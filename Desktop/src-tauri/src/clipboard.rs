#[cfg(target_os = "macos")]
mod native {
    use objc2_app_kit::NSPasteboard;
    use objc2_foundation::{NSData, NSString};
    const STEPS: [&str; 3] = [
        "CorePasteboardFlavorType 0x584D5353",
        "dyn.ah62d4rv4gk8zuxnxnq",
        "com.apple.ostype:XMSS",
    ];
    const SCRIPTS: [&str; 2] = [
        "CorePasteboardFlavorType 0x584D5343",
        "com.apple.ostype:XMSC",
    ];
    pub fn read_text() -> Result<String, String> {
        NSPasteboard::generalPasteboard()
            .stringForType(&NSString::from_str("public.utf8-plain-text"))
            .map(|s| s.to_string())
            .ok_or("Copy readable script text first.".into())
    }
    pub fn read_xml() -> Result<String, String> {
        let pb = NSPasteboard::generalPasteboard();
        for name in STEPS.into_iter().chain(SCRIPTS) {
            if let Some(data) = pb.dataForType(&NSString::from_str(name)) {
                return crate::codec::decode_xml(&data.to_vec());
            }
        }
        Err("Copy script steps or a script in FileMaker Pro first.".into())
    }
    pub fn write_text(text: &str, _owner: isize) -> Result<(), String> {
        let pb = NSPasteboard::generalPasteboard();
        pb.clearContents();
        if pb.setString_forType(
            &NSString::from_str(text),
            &NSString::from_str("public.utf8-plain-text"),
        ) {
            Ok(())
        } else {
            Err("macOS could not update the clipboard.".into())
        }
    }
    pub fn write_xml(xml: &str, _owner: isize) -> Result<(), String> {
        let pb = NSPasteboard::generalPasteboard();
        let data = NSData::with_bytes(xml.as_bytes());
        pb.clearContents();
        for name in STEPS {
            if !pb.setData_forType(Some(&data), &NSString::from_str(name)) {
                return Err("macOS did not accept the native FileMaker clipboard.".into());
            }
        }
        let _ = pb.setString_forType(
            &NSString::from_str(xml),
            &NSString::from_str("public.utf8-plain-text"),
        );
        Ok(())
    }
    pub fn types() -> Vec<String> {
        NSPasteboard::generalPasteboard()
            .types()
            .map(|a| a.iter().map(|s| s.to_string()).collect())
            .unwrap_or_default()
    }
}

#[cfg(windows)]
mod native {
    use std::{ffi::c_void, ptr::null_mut};
    type Handle = *mut c_void;
    #[link(name = "user32")]
    unsafe extern "system" {
        fn OpenClipboard(owner: Handle) -> i32;
        fn CloseClipboard() -> i32;
        fn EmptyClipboard() -> i32;
        fn RegisterClipboardFormatW(name: *const u16) -> u32;
        fn GetClipboardData(format: u32) -> Handle;
        fn SetClipboardData(format: u32, data: Handle) -> Handle;
        fn EnumClipboardFormats(format: u32) -> u32;
        fn GetClipboardFormatNameW(format: u32, name: *mut u16, len: i32) -> i32;
    }
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn GlobalAlloc(flags: u32, bytes: usize) -> Handle;
        fn GlobalLock(data: Handle) -> Handle;
        fn GlobalUnlock(data: Handle) -> i32;
        fn GlobalFree(data: Handle) -> Handle;
        fn GlobalSize(data: Handle) -> usize;
    }
    struct Open;
    impl Drop for Open {
        fn drop(&mut self) {
            unsafe {
                CloseClipboard();
            }
        }
    }
    fn open(owner: isize) -> Result<Open, String> {
        for _ in 0..10 {
            if unsafe { OpenClipboard(owner as Handle) } != 0 {
                return Ok(Open);
            }
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
        Err("The clipboard is busy. Try again.".into())
    }
    fn format(name: &str) -> Result<u32, String> {
        let wide: Vec<u16> = name.encode_utf16().chain([0]).collect();
        let id = unsafe { RegisterClipboardFormatW(wide.as_ptr()) };
        if id == 0 {
            Err("Could not register the FileMaker clipboard format.".into())
        } else {
            Ok(id)
        }
    }
    // Global memory transfers to Windows only after SetClipboardData succeeds.
    struct Memory(Handle);
    impl Drop for Memory {
        fn drop(&mut self) {
            if !self.0.is_null() {
                unsafe {
                    GlobalFree(self.0);
                }
            }
        }
    }
    fn allocate(bytes: &[u8]) -> Result<Memory, String> {
        unsafe {
            let block = Memory(GlobalAlloc(0x0042, bytes.len()));
            if block.0.is_null() {
                return Err("Clipboard allocation failed".into());
            }
            let ptr = GlobalLock(block.0);
            if ptr.is_null() {
                return Err("Clipboard lock failed".into());
            }
            std::ptr::copy_nonoverlapping(bytes.as_ptr(), ptr as *mut u8, bytes.len());
            GlobalUnlock(block.0);
            Ok(block)
        }
    }
    fn read(format: u32) -> Result<Vec<u8>, String> {
        unsafe {
            let data = GetClipboardData(format);
            if data.is_null() {
                return Err("Copy the required content first.".into());
            }
            let size = GlobalSize(data);
            if size == 0 || size > 16 * 1024 * 1024 + 4 {
                return Err("Clipboard payload has an invalid size.".into());
            }
            let ptr = GlobalLock(data);
            if ptr.is_null() {
                return Err("Clipboard lock failed".into());
            }
            let bytes = std::slice::from_raw_parts(ptr as *const u8, size).to_vec();
            GlobalUnlock(data);
            Ok(bytes)
        }
    }
    fn write(entries: Vec<(u32, Vec<u8>)>, owner: isize) -> Result<(), String> {
        if owner == 0 {
            return Err("The app window is unavailable for clipboard ownership.".into());
        }
        let mut blocks = entries
            .into_iter()
            .map(|(f, b)| allocate(&b).map(|m| (f, m)))
            .collect::<Result<Vec<_>, _>>()?;
        let _guard = open(owner)?;
        if unsafe { EmptyClipboard() } == 0 {
            return Err("Could not clear the clipboard.".into());
        }
        for (f, block) in &mut blocks {
            if unsafe { SetClipboardData(*f, block.0) }.is_null() {
                return Err("Windows did not accept the clipboard data.".into());
            }
            block.0 = null_mut();
        }
        Ok(())
    }
    fn text_bytes(text: &str) -> Vec<u8> {
        text.encode_utf16()
            .chain([0])
            .flat_map(u16::to_le_bytes)
            .collect()
    }
    pub fn read_text() -> Result<String, String> {
        let _guard = open(0)?;
        let bytes = read(13)?;
        let units: Vec<u16> = bytes
            .chunks_exact(2)
            .map(|b| u16::from_le_bytes([b[0], b[1]]))
            .take_while(|u| *u != 0)
            .collect();
        String::from_utf16(&units).map_err(|_| "Clipboard text is invalid UTF-16.".into())
    }
    pub fn read_xml() -> Result<String, String> {
        let _guard = open(0)?;
        for name in ["Mac-XMSS", "Mac-XMSC"] {
            if let Ok(data) = read(format(name)?) {
                return crate::codec::windows_xml(&data);
            }
        }
        Err("Copy script steps or a script in FileMaker Pro first.".into())
    }
    pub fn write_text(text: &str, owner: isize) -> Result<(), String> {
        write(vec![(13, text_bytes(text))], owner)
    }
    pub fn write_xml(xml: &str, owner: isize) -> Result<(), String> {
        write(
            vec![
                (format("Mac-XMSS")?, crate::codec::windows_payload(xml)?),
                (13, text_bytes(xml)),
            ],
            owner,
        )
    }
    pub fn types() -> Vec<String> {
        let Ok(_guard) = open(0) else { return vec![] };
        let mut output = vec![];
        let mut f = 0;
        loop {
            f = unsafe { EnumClipboardFormats(f) };
            if f == 0 {
                break;
            }
            let mut buf = [0u16; 256];
            let n = unsafe { GetClipboardFormatNameW(f, buf.as_mut_ptr(), 256) };
            output.push(if n > 0 {
                String::from_utf16_lossy(&buf[..n as usize])
            } else {
                format!("Windows format {f}")
            });
        }
        output
    }
}
#[cfg(not(any(target_os = "macos", windows)))]
mod native {
    pub fn read_text() -> Result<String, String> {
        Err("This desktop targets macOS and Windows.".into())
    }
    pub fn read_xml() -> Result<String, String> {
        read_text()
    }
    pub fn write_text(_: &str, _: isize) -> Result<(), String> {
        Err("Unsupported clipboard platform".into())
    }
    pub fn write_xml(s: &str, o: isize) -> Result<(), String> {
        write_text(s, o)
    }
    pub fn types() -> Vec<String> {
        vec![]
    }
}
pub use native::*;
