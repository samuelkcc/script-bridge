#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]
mod ai;
mod clipboard;
mod codec;
mod knowledge;
mod worker;
use serde_json::{json, Value};
use std::sync::Mutex;
use tauri::{Manager, State};
struct Host {
    worker: Mutex<Option<worker::Worker>>,
    ai: Mutex<Option<std::sync::Arc<ai::AiService>>>,
}

#[tauri::command]
async fn bridge(
    app: tauri::AppHandle,
    state: State<'_, Host>,
    op: String,
    payload: Value,
) -> Result<Value, String> {
    let host = app.clone();
    let owner: isize = {
        #[cfg(windows)]
        {
            app.get_webview_window("main")
                .ok_or("App window unavailable")?
                .hwnd()
                .map_err(|e| e.to_string())?
                .0 as isize
        }
        #[cfg(not(windows))]
        {
            0
        }
    };
    // Clone no script state. The owned host handle keeps managed state alive.
    let _ = state;
    tauri::async_runtime::spawn_blocking(move || {
        let state=host.state::<Host>();
        if op.starts_with("ai_") {
            let service = {
                let mut slot = state.ai.lock().map_err(|e| e.to_string())?;
                if slot.is_none() { *slot = Some(ai::AiService::new(host.path().app_data_dir().map_err(|e|e.to_string())?.join("ai"))?); }
                slot.as_ref().unwrap().clone()
            };
            match op.as_str() {
                "ai_status" => return Ok(service.status()),
                "ai_download" => {service.download(payload["model"].as_str().unwrap_or_default())?;return Ok(service.status());},
                "ai_cancel" => {service.cancel();return Ok(service.status());},
                "ai_unload" => {service.unload()?;return Ok(service.status());},
                "ai_remove" => {service.remove(payload["model"].as_str().unwrap_or_default())?;return Ok(service.status());},
                "ai_generate" => {
                    let app = host.clone();
                    service.generate(payload,move |source| {
                        let state=app.state::<Host>();
                        let mut slot=state.worker.lock().map_err(|_|"Conversion session lock failed")?;
                        if slot.is_none(){*slot=Some(worker::Worker::start()?);}
                        slot.as_mut().unwrap().call(json!({"op":"compile","source":source,"templates":false}))
                    })?;
                    return Ok(service.status());
                },
                _ => return Err("Unsupported AI operation".into())
            }
        }
        if op=="openLink" {
            let raw=payload["url"].as_str().ok_or("No link supplied")?;
            let url=tauri::Url::parse(raw).map_err(|_|"Invalid link")?;
            if url.scheme()!="https" || url.host_str().is_none() || !url.username().is_empty() || url.password().is_some() {return Err("Only public HTTPS links can be opened.".into());}
            #[cfg(target_os="macos")] {
                let status=std::process::Command::new("/usr/bin/open").arg(url.as_str()).status().map_err(|e|e.to_string())?;
                if !status.success(){return Err("The system browser could not open this link.".into());}
            }
            #[cfg(windows)] {
                use std::{ffi::c_void,ptr::null};
                #[link(name="shell32")] unsafe extern "system" {fn ShellExecuteW(owner:*mut c_void,verb:*const u16,file:*const u16,params:*const u16,dir:*const u16,show:i32)->*mut c_void;}
                let wide:Vec<u16>=url.as_str().encode_utf16().chain([0]).collect();
                let result=unsafe{ShellExecuteW(owner as *mut c_void,null(),wide.as_ptr(),null(),null(),1)};
                if (result as isize)<=32{return Err("The system browser could not open this link.".into());}
            }
            return Ok(json!({"opened":true}));
        }
        if op=="inspect" {return Ok(json!({"types":clipboard::types()}));}
        if op=="pasteText" {return Ok(json!({"text":clipboard::read_text()?}));}
        if op=="copyText" {
            let text=payload["text"].as_str().ok_or("No text to copy")?;
            if text.len()>16*1024*1024{return Err("Text exceeds the clipboard limit".into());}
            clipboard::write_text(text,owner)?; return Ok(json!({"copied":true}));
        }
        let mut slot=state.worker.lock().map_err(|_|"Conversion session lock failed")?;
        if slot.is_none(){*slot=Some(worker::Worker::start()?);}
        let engine=slot.as_mut().unwrap();
        match op.as_str(){
            "hello"|"compile"|"reset"|"review"|"applyFixes"=>{
                let mut request=payload.as_object().cloned().unwrap_or_default();request.insert("op".into(),json!(op));engine.call(Value::Object(request))
            },
            "import"=>{
                let xml=clipboard::read_xml()?;
                let result=engine.call(json!({"op":"decompile","xml":xml,"templates":payload["templates"]}))?;
                // Import remains visible even if the OS refuses the secondary text copy.
                let mut result=result;
                let copied=clipboard::write_text(result["source"].as_str().unwrap_or_default(),owner);
                result["textCopied"]=json!(copied.is_ok());
                if let Err(error)=copied {result["clipboardError"]=json!(error);}
                Ok(result)
            },
            "copyNative"=>{
                // Never trust a webview's canCopy flag or XML. Compile again in
                // the authoritative session immediately before the native write.
                let result=engine.call(json!({"op":"compile","source":payload["source"],"templates":payload["templates"]}))?;
                if result["canCopy"]!=true{return Err("Resolve blocking issues before creating the native clipboard.".into());}
                clipboard::write_xml(result["xml"].as_str().ok_or("No compiled XML")?,owner)?;
                Ok(result)
            },
            _=>Err("Unsupported desktop operation".into())
        }
    }).await.map_err(|e|e.to_string())?
}
fn main() {
    tauri::Builder::default()
        .manage(Host {
            worker: Mutex::new(None),
            ai: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![bridge])
        .build(tauri::generate_context!())
        .expect("Could not start FileMaker Script Bridge")
        .run(|app, event| {
            if matches!(
                event,
                tauri::RunEvent::Exit | tauri::RunEvent::ExitRequested { .. }
            ) {
                if let Ok(slot) = app.state::<Host>().ai.lock() {
                    if let Some(service) = slot.as_ref() {
                        service.cancel();
                    }
                }
            }
        });
}
