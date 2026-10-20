// FileMaker Windows uses registered Mac-XMSS / Mac-XMSC formats with a
// little-endian u32 UTF-8 byte length followed by XML. macOS uses raw XML.
const LIMIT: usize = 16 * 1024 * 1024;
#[cfg(any(windows, test))]
pub fn windows_payload(xml: &str) -> Result<Vec<u8>, String> {
    if xml.len() > LIMIT {
        return Err("XML exceeds the clipboard limit".into());
    }
    let mut data = (xml.len() as u32).to_le_bytes().to_vec();
    data.extend_from_slice(xml.as_bytes());
    Ok(data)
}
#[cfg(any(windows, test))]
pub fn windows_xml(data: &[u8]) -> Result<String, String> {
    let header: [u8; 4] = data
        .get(..4)
        .ok_or("Truncated FileMaker length header")?
        .try_into()
        .unwrap();
    let len = u32::from_le_bytes(header) as usize;
    if len > LIMIT {
        return Err("XML exceeds the clipboard limit".into());
    }
    let body = data.get(4..4 + len).ok_or("Truncated FileMaker XML")?;
    decode_xml(body)
}
pub fn decode_xml(data: &[u8]) -> Result<String, String> {
    if data.len() > LIMIT {
        return Err("XML exceeds the clipboard limit".into());
    }
    let utf8 = String::from_utf8(data.to_vec()).ok();
    let xml = if utf8
        .as_ref()
        .is_some_and(|s| s.contains("<fmxmlsnippet") || s.contains("<FMObjectTransfer"))
    {
        utf8.unwrap()
    } else {
        if data.len() % 2 != 0 {
            return Err("Clipboard XML encoding is invalid".into());
        }
        let be = data.starts_with(&[0xfe, 0xff]) || data.starts_with(&[0, b'<']);
        let units: Vec<u16> = data
            .chunks_exact(2)
            .map(|b| {
                if be {
                    u16::from_be_bytes([b[0], b[1]])
                } else {
                    u16::from_le_bytes([b[0], b[1]])
                }
            })
            .collect();
        String::from_utf16(&units).map_err(|_| "Clipboard XML encoding is invalid")?
    };
    let xml = xml.trim_matches(['\0', '\u{feff}']).to_owned();
    if !xml.contains("<fmxmlsnippet") && !xml.contains("<FMObjectTransfer") {
        return Err("Clipboard does not contain FileMaker XML".into());
    }
    Ok(xml)
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn windows_length_counts_utf8_bytes() {
        let xml = "<fmxmlsnippet><Step name=\"廣東話 🎵\"/></fmxmlsnippet>";
        let data = windows_payload(xml).unwrap();
        assert_eq!(
            u32::from_le_bytes(data[..4].try_into().unwrap()) as usize,
            xml.len()
        );
        assert_eq!(windows_xml(&data).unwrap(), xml);
    }
    #[test]
    fn rejects_truncation_and_unbounded_header() {
        assert!(windows_xml(&[1, 2, 3]).is_err());
        assert!(windows_xml(&[255, 255, 255, 255]).is_err());
        let mut data = windows_payload("<fmxmlsnippet/>").unwrap();
        data.pop();
        assert!(windows_xml(&data).is_err());
    }
    #[test]
    fn decodes_utf16_and_rejects_plain_text() {
        let xml = "<fmxmlsnippet/>";
        for be in [true, false] {
            let bytes: Vec<u8> = xml
                .encode_utf16()
                .flat_map(|u| if be { u.to_be_bytes() } else { u.to_le_bytes() })
                .collect();
            assert_eq!(decode_xml(&bytes).unwrap(), xml);
        }
        assert!(decode_xml(b"ordinary text").is_err());
    }
}
