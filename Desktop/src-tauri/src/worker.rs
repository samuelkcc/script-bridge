use serde_json::{json, Value};
use std::{
    io::{BufRead, BufReader, Write},
    path::PathBuf,
    process::{Child, ChildStdin, Command, Stdio},
    sync::mpsc::{self, Receiver},
    time::Duration,
};

pub struct Worker {
    child: Child,
    input: ChildStdin,
    output: Receiver<Result<String, String>>,
    failed: bool,
}
impl Worker {
    pub fn start() -> Result<Self, String> {
        let exe = std::env::current_exe().map_err(|e| e.to_string())?;
        let name = if cfg!(windows) {
            "FileMakerBridgeWorker.exe"
        } else {
            "FileMakerBridgeWorker"
        };
        let packaged = exe
            .parent()
            .ok_or("Application folder unavailable")?
            .join(name);
        let path = if cfg!(debug_assertions) && !packaged.is_file() {
            PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("../../.build/desktop-worker/debug")
                .join(name)
        } else {
            packaged
        };
        let mut command = Command::new(path);
        command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000);
        }
        let mut child = command.spawn().map_err(|e| {
            format!("Conversion worker unavailable. Build or reinstall the desktop package: {e}")
        })?;
        let input = child.stdin.take().ok_or("Worker input unavailable")?;
        let stdout = child.stdout.take().ok_or("Worker output unavailable")?;
        let (tx, output) = mpsc::channel();
        std::thread::spawn(move || {
            for line in BufReader::new(stdout).lines() {
                if tx.send(line.map_err(|e| e.to_string())).is_err() {
                    break;
                }
            }
        });
        let mut worker = Self {
            child,
            input,
            output,
            failed: false,
        };
        let hello = worker.call(json!({"op":"hello"}))?;
        if hello["protocol"] != 1 {
            return Err(
                "Incompatible conversion worker. Reinstall matching app and worker.".into(),
            );
        }
        Ok(worker)
    }
    pub fn call(&mut self, request: Value) -> Result<Value, String> {
        if self.failed {
            return Err("The conversion session ended. Restart the app and re-import the original FileMaker script; locked steps cannot be recovered from their markers.".into());
        }
        let raw = serde_json::to_vec(&request).map_err(|e| e.to_string())?;
        if raw.len() > 24 * 1024 * 1024 {
            return Err("Request exceeds the desktop limit.".into());
        }
        if self
            .input
            .write_all(&raw)
            .and_then(|_| self.input.write_all(b"\n"))
            .and_then(|_| self.input.flush())
            .is_err()
        {
            return self.fail();
        }
        let line = match self.output.recv_timeout(Duration::from_secs(30)) {
            Ok(Ok(line)) => line,
            _ => return self.fail(),
        };
        let value: Value = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(_) => return self.fail(),
        };
        if value["ok"] == true {
            Ok(value["result"].clone())
        } else {
            Err(value["error"]
                .as_str()
                .unwrap_or("Conversion failed")
                .into())
        }
    }
    fn fail(&mut self) -> Result<Value, String> {
        self.failed = true;
        let _ = self.child.kill();
        let _ = self.child.wait();
        Err("The conversion worker stopped or timed out. Restart the app and re-import the original FileMaker script. The clipboard was not updated.".into())
    }
}
impl Drop for Worker {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}
