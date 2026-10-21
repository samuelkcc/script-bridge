use fs2::FileExt;
use reqwest::blocking::Client;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    fs::{self, File, OpenOptions},
    io::{BufRead, BufReader, Read, Write},
    net::TcpListener,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicBool, AtomicU64, Ordering},
        Arc, Mutex, OnceLock,
    },
    time::{Duration, Instant},
};

const LIMIT: usize = 1024 * 1024;
fn catalogue() -> &'static Value {
    static DATA: OnceLock<Value> = OnceLock::new();
    DATA.get_or_init(|| {
        serde_json::from_str(include_str!("../../ai/catalogue.json")).expect("Bundled AI catalogue")
    })
}
fn model(id: &str) -> Result<Value, String> {
    catalogue()["models"]
        .as_array()
        .unwrap()
        .iter()
        .find(|m| m["id"] == id)
        .cloned()
        .ok_or("Choose one of the available Gemma or Qwen models.".into())
}
fn text<'a>(v: &'a Value, key: &str) -> &'a str {
    v[key].as_str().unwrap_or_default()
}
fn bytes(v: &Value) -> u64 {
    v["bytes"].as_u64().unwrap_or(0)
}
fn modified(path: &Path) -> u64 {
    path.metadata()
        .and_then(|m| m.modified())
        .ok()
        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
        .map(|d| d.as_secs())
        .unwrap_or(0)
}
fn runtime_target() -> &'static str {
    if cfg!(windows) {
        "windows-x64"
    } else if cfg!(target_arch = "aarch64") {
        "macos-arm64"
    } else {
        "macos-x64"
    }
}
struct Server {
    child: Child,
    model: String,
    address: String,
    key: String,
}
impl Drop for Server {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

pub struct AiService {
    root: PathBuf,
    runtime: PathBuf,
    progress: Mutex<Value>,
    busy: AtomicBool,
    revision: AtomicU64,
    cancelled: AtomicBool,
    server: Mutex<Option<Server>>,
}
impl AiService {
    pub fn new(root: PathBuf) -> Result<Arc<Self>, String> {
        fs::create_dir_all(root.join("models")).map_err(|e| e.to_string())?;
        let exe = std::env::current_exe().map_err(|e| e.to_string())?;
        let folder = if cfg!(target_os = "macos") {
            exe.parent().unwrap().join("../Resources/ai-runtime")
        } else {
            exe.parent().unwrap().join("ai-runtime")
        };
        let runtime = if cfg!(debug_assertions) && !folder.is_dir() {
            PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("../../.build/ai-runtime")
                .join(runtime_target())
        } else {
            folder
        };
        Ok(Arc::new(Self {
            root,
            runtime,
            progress: Mutex::new(
                json!({"phase":"idle","message":"Choose a model to get started."}),
            ),
            busy: AtomicBool::new(false),
            revision: AtomicU64::new(0),
            cancelled: AtomicBool::new(false),
            server: Mutex::new(None),
        }))
    }
    fn path(&self, m: &Value) -> PathBuf {
        self.root.join("models").join(text(m, "filename"))
    }
    fn installed(&self, m: &Value) -> bool {
        let path = self.path(m);
        let receipt = fs::read(path.with_extension("verified.json"))
            .ok()
            .and_then(|d| serde_json::from_slice::<Value>(&d).ok());
        path.metadata().is_ok_and(|meta| meta.len() == bytes(m))
            && receipt.is_some_and(|r| {
                r["sha256"] == m["sha256"]
                    && r["bytes"] == m["bytes"]
                    && r["modified"] == modified(&path)
            })
    }
    pub fn status(&self) -> Value {
        let rows: Vec<Value> = catalogue()["models"]
            .as_array()
            .unwrap()
            .iter()
            .map(|m| {
                let mut row = m.clone();
                row["installed"] = json!(self.installed(m));
                row["hasFiles"] = json!(
                    self.path(m).exists()
                        || self.path(m).with_extension("part").exists()
                        || self.path(m).with_extension("verified.json").exists()
                );
                row["partialBytes"] = json!(self
                    .path(m)
                    .with_extension("part")
                    .metadata()
                    .map(|m| m.len())
                    .unwrap_or(0));
                row
            })
            .collect();
        let running = self
            .server
            .try_lock()
            .ok()
            .and_then(|s| s.as_ref().map(|s| s.model.clone()));
        json!({"models":rows,"revision":self.revision.load(Ordering::SeqCst),"busy":self.busy.load(Ordering::SeqCst),"operation":self.progress.lock().map(|v|v.clone()).unwrap_or(Value::Null),"loadedModel":running,"runtimeReady":self.runtime.join(if cfg!(windows){"llama-server.exe"}else{"llama-server"}).is_file(),"systemMemoryGB":physical_memory_gb(),"freeDiskBytes":fs2::available_space(&self.root).ok(),"runtimeVersion":catalogue()["runtime"]["version"]})
    }
    fn update(&self, phase: &str, message: &str, extra: Value) {
        let mut value = extra.as_object().cloned().unwrap_or_default();
        value.insert("phase".into(), json!(phase));
        value.insert("message".into(), json!(message));
        if let Ok(mut p) = self.progress.lock() {
            *p = Value::Object(value);
        }
    }
    fn begin(&self) -> Result<(), String> {
        if self.busy.swap(true, Ordering::SeqCst) {
            return Err("Wait for the current AI operation or cancel it first.".into());
        }
        self.revision.fetch_add(1, Ordering::SeqCst);
        self.cancelled.store(false, Ordering::SeqCst);
        Ok(())
    }
    fn check_cancel(&self) -> Result<(), String> {
        if self.cancelled.load(Ordering::SeqCst) {
            Err("Operation cancelled.".into())
        } else {
            Ok(())
        }
    }
    fn finish(&self, result: Result<(), String>) {
        if let Err(error) = result {
            self.update(
                if self.cancelled.load(Ordering::SeqCst) {
                    "cancelled"
                } else {
                    "error"
                },
                &error,
                json!({}),
            );
        }
        self.busy.store(false, Ordering::SeqCst);
    }
    pub fn cancel(&self) {
        self.cancelled.store(true, Ordering::SeqCst);
        if let Ok(mut server) = self.server.lock() {
            *server = None;
        }
    }
    pub fn unload(&self) -> Result<(), String> {
        if self.busy.load(Ordering::SeqCst) {
            return Err("Cancel the current operation before releasing the model.".into());
        }
        *self.server.lock().map_err(|e| e.to_string())? = None;
        Ok(())
    }
    pub fn remove(&self, id: &str) -> Result<(), String> {
        let m = model(id)?;
        self.begin()?;
        let result = (|| {
            let lock = OpenOptions::new()
                .create(true)
                .truncate(false)
                .read(true)
                .write(true)
                .open(self.root.join("model-download.lock"))
                .map_err(|e| e.to_string())?;
            lock.try_lock_exclusive().map_err(|_| {
                "Another app window is using the model download files. Wait for it to finish."
                    .to_string()
            })?;
            let mut server = self.server.lock().map_err(|e| e.to_string())?;
            if server.as_ref().is_some_and(|s| s.model == id) {
                *server = None;
            }
            drop(server);
            let path = self.path(&m);
            for file in [
                &path,
                &path.with_extension("part"),
                &path.with_extension("verified.json"),
            ] {
                match fs::remove_file(file) {
                    Ok(()) => {}
                    Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
                    Err(e) => return Err(format!("Could not remove this model: {e}")),
                }
            }
            self.update(
                "complete",
                "Model removed from this computer. Select it again to download it.",
                json!({"model":id}),
            );
            Ok(())
        })();
        self.finish(result.clone());
        result
    }
    pub fn download(self: &Arc<Self>, id: &str) -> Result<(), String> {
        let m = model(id)?;
        self.begin()?;
        let service = self.clone();
        self.update(
            "downloading",
            "Preparing the model download…",
            json!({"model":id,"received":0,"total":bytes(&m)}),
        );
        std::thread::spawn(move || {
            let result = service.download_model(&m);
            service.finish(result);
        });
        Ok(())
    }
    fn download_model(&self, m: &Value) -> Result<(), String> {
        let lock = OpenOptions::new()
            .create(true)
            .truncate(false)
            .read(true)
            .write(true)
            .open(self.root.join("model-download.lock"))
            .map_err(|e| e.to_string())?;
        lock.try_lock_exclusive()
            .map_err(|_| "Another app window is downloading a model. Wait for it to finish.")?;
        if self.installed(m) {
            self.update(
                "complete",
                "Model is already downloaded and verified.",
                json!({"model":m["id"]}),
            );
            return Ok(());
        }
        let path = self.path(m);
        let part = path.with_extension("part");
        let expected = bytes(m);
        let mut received = part.metadata().map(|m| m.len()).unwrap_or(0);
        if received > expected {
            fs::remove_file(&part).map_err(|e| e.to_string())?;
            received = 0;
        }
        let free = fs2::available_space(&self.root).map_err(|e| e.to_string())?;
        if free < expected - received + 512 * 1024 * 1024 {
            return Err("There is not enough free disk space for this model.".into());
        }
        let mut hash = Sha256::new();
        let mut buffer = vec![0u8; LIMIT];
        if received > 0 {
            self.update(
                "verifying",
                "Checking the partial download before resuming…",
                json!({"model":m["id"],"received":received,"total":expected}),
            );
            let mut existing = File::open(&part).map_err(|e| e.to_string())?;
            loop {
                self.check_cancel()?;
                let n = existing.read(&mut buffer).map_err(|e| e.to_string())?;
                if n == 0 {
                    break;
                }
                hash.update(&buffer[..n]);
            }
        }
        if received < expected {
            let runtime = tokio::runtime::Builder::new_current_thread()
                .enable_all()
                .build()
                .map_err(|e| e.to_string())?;
            runtime.block_on(async {
                let client=reqwest::Client::builder().connect_timeout(Duration::from_secs(30)).read_timeout(Duration::from_secs(30)).user_agent("FileMakerScriptBridge/1.0.0").build().map_err(|e|e.to_string())?;
                let mut request=client.get(text(m,"url"));if received>0{request=request.header(reqwest::header::RANGE,format!("bytes={received}-"));}
                let mut sending=std::pin::pin!(request.send());
                let mut response=loop {
                    self.check_cancel()?;
                    match tokio::time::timeout(Duration::from_millis(250),&mut sending).await {
                        Ok(response)=>break response.and_then(|r|r.error_for_status()).map_err(|e|format!("Model download failed: {e}. Choose Resume to try again."))?,
                        Err(_)=>continue
                    }
                };
                if received>0 && response.status()==reqwest::StatusCode::OK {
                    File::create(&part).map_err(|e|e.to_string())?;received=0;hash=Sha256::new();
                } else if received>0 && (response.status()!=reqwest::StatusCode::PARTIAL_CONTENT || !response.headers().get(reqwest::header::CONTENT_RANGE).and_then(|h|h.to_str().ok()).is_some_and(|s|s.starts_with(&format!("bytes {received}-")))) {
                    let _=fs::remove_file(&part);
                    return Err("The server returned an invalid resume range. Choose Download again to start a clean download.".to_string());
                }
                let mut output=OpenOptions::new().create(true).append(true).open(&part).map_err(|e|e.to_string())?;
                let mut update=Instant::now()-Duration::from_secs(1);
                loop {
                    self.check_cancel()?;
                    let chunk=match tokio::time::timeout(Duration::from_millis(250),response.chunk()).await {
                        Err(_)=>continue,
                        Ok(chunk)=>chunk.map_err(|e|format!("Download interrupted: {e}. Choose Resume to continue."))?
                    };
                    let Some(chunk)=chunk else {break};
                    received+=chunk.len() as u64;if received>expected{return Err("Download exceeded its pinned size. The file was not installed.".into());}
                    output.write_all(&chunk).map_err(|e|e.to_string())?;hash.update(&chunk);
                    if update.elapsed()>Duration::from_millis(200){self.update("downloading","Downloading the selected AI model…",json!({"model":m["id"],"received":received,"total":expected}));update=Instant::now();}
                }
                output.sync_all().map_err(|e|e.to_string())?;
                Ok::<(),String>(())
            })?;
        }
        self.check_cancel()?;
        self.update(
            "verifying",
            "Verifying the complete model checksum…",
            json!({"model":m["id"],"received":received,"total":expected}),
        );
        if received != expected || format!("{:x}", hash.finalize()) != text(m, "sha256") {
            let _ = fs::remove_file(&part);
            return Err("The model did not match its pinned size and SHA-256. It was not installed. Download it again.".into());
        }
        fs::rename(&part, &path).map_err(|e| e.to_string())?;
        fs::write(path.with_extension("verified.json"),serde_json::to_vec(&json!({"sha256":m["sha256"],"bytes":expected,"modified":modified(&path),"revision":m["revision"]})).unwrap()).map_err(|e|e.to_string())?;
        self.update(
            "complete",
            "Model downloaded and verified. You can generate a script now.",
            json!({"model":m["id"]}),
        );
        Ok(())
    }
    fn ensure_server(&self, m: &Value) -> Result<(String, String), String> {
        self.check_cancel()?;
        if !self.installed(m) {
            return Err("Download and verify the selected model first.".into());
        }
        if physical_memory_gb()
            .is_some_and(|gb| gb < m["estimatedModelGB"].as_f64().unwrap_or(0.) + 3.)
        {
            return Err("This model is larger than this computer's safe memory budget. Choose a lighter model or use a computer with more memory.".into());
        }
        let mut server = self.server.lock().map_err(|e| e.to_string())?;
        if let Some(s) = server.as_mut() {
            if s.model == m["id"] && s.child.try_wait().map_err(|e| e.to_string())?.is_none() {
                return Ok((s.address.clone(), s.key.clone()));
            }
        }
        *server = None;
        let executable = self.runtime.join(if cfg!(windows) {
            "llama-server.exe"
        } else {
            "llama-server"
        });
        if !executable.is_file() {
            return Err(
                "The bundled AI runtime is missing. Rebuild or reinstall the complete app.".into(),
            );
        }
        let port = TcpListener::bind("127.0.0.1:0")
            .and_then(|l| l.local_addr())
            .map_err(|e| e.to_string())?
            .port();
        let key = uuid::Uuid::new_v4().to_string();
        let address = format!("http://127.0.0.1:{port}");
        let mut command = Command::new(executable);
        command
            .current_dir(&self.runtime)
            .args(["--model"])
            .arg(self.path(m))
            .args([
                "--host",
                "127.0.0.1",
                "--port",
                &port.to_string(),
                "--ctx-size",
                "32768",
                "--parallel",
                "1",
                "--api-key",
                &key,
                "--jinja",
                "--reasoning",
                "off",
                "--no-webui",
                "--log-disable",
                "--threads",
                &std::thread::available_parallelism()
                    .map(|n| n.get().min(8))
                    .unwrap_or(4)
                    .to_string(),
                "--n-gpu-layers",
                if cfg!(target_os = "macos") { "99" } else { "0" },
            ]);
        command
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000);
        }
        let child = command
            .spawn()
            .map_err(|e| format!("Could not start the bundled AI engine: {e}"))?;
        *server = Some(Server {
            child,
            model: text(m, "id").into(),
            address: address.clone(),
            key: key.clone(),
        });
        // Never hold the process lock across network health checks. Cancel and
        // app exit must be able to stop a model immediately while it loads.
        drop(server);
        let client = Client::builder()
            .no_proxy()
            .timeout(Duration::from_secs(2))
            .build()
            .map_err(|e| e.to_string())?;
        let start = Instant::now();
        loop {
            if let Err(e) = self.check_cancel() {
                self.cancel();
                return Err(e);
            }
            {
                let mut server = self.server.lock().map_err(|e| e.to_string())?;
                let Some(running) = server.as_mut() else {
                    return Err("The AI engine was stopped.".into());
                };
                if running
                    .child
                    .try_wait()
                    .map_err(|e| e.to_string())?
                    .is_some()
                {
                    *server = None;
                    return Err("The AI engine could not load this model. Free memory and try again, or choose Gemma 4 E4B.".into());
                }
            }
            if client
                .get(format!("{address}/health"))
                .bearer_auth(&key)
                .send()
                .is_ok_and(|r| r.status().is_success())
            {
                return Ok((address, key));
            }
            if start.elapsed() > Duration::from_secs(300) {
                *self.server.lock().map_err(|e| e.to_string())? = None;
                return Err(
                    "The model did not become ready within five minutes. Try the smaller model."
                        .into(),
                );
            }
            std::thread::sleep(Duration::from_millis(250));
        }
    }
    pub fn generate<F>(self: &Arc<Self>, params: Value, validate: F) -> Result<(), String>
    where
        F: Fn(&str) -> Result<Value, String> + Send + 'static,
    {
        let id = text(&params, "model");
        let m = model(id)?;
        let question = text(&params, "question").trim();
        if question.len() < 3 || question.len() > 6000 {
            return Err("Enter a question between 3 and 6,000 characters.".into());
        }
        if text(&params, "schema").len() > 6000 || text(&params, "existing").len() > 120000 {
            return Err(
                "Shorten the database context or existing script before generating.".into(),
            );
        }
        validate_attachment(&params["attachment"])?;
        self.begin()?;
        let service = self.clone();
        self.update(
            "loading",
            "Loading the selected AI model…",
            json!({"model":id}),
        );
        std::thread::spawn(move || {
            let result = service.generate_script(&m, &params, validate);
            service.finish(result);
        });
        Ok(())
    }
    fn generate_script<F>(&self, m: &Value, params: &Value, validate: F) -> Result<(), String>
    where
        F: Fn(&str) -> Result<Value, String>,
    {
        let (address, key) = self.ensure_server(m)?;
        let (mut messages, sections) = crate::knowledge::messages(
            text(params, "question"),
            text(params, "schema"),
            text(params, "existing"),
            &params["attachment"],
        );
        let source = format!(
            "{}\n{}",
            text(params, "existing"),
            text(&params["attachment"], "text")
        );
        let source_tokens = self.token_count(&address, &key, &source)?;
        let mut script = self.completion(&address, &key, &messages, &sections, 0, source_tokens)?;
        if script.is_empty() {
            return Err("The model returned no script. Try a more specific question.".into());
        }
        let mut validation = validate(&script)?;
        if validation["errorCount"].as_u64().unwrap_or(0) > 0 {
            self.update(
                "repairing",
                "The validator found unsupported syntax. Asking the model for one repair…",
                json!({"model":m["id"],"script":script,"sections":sections}),
            );
            let issues = validation["issues"]
                .as_array()
                .map(|a| a.iter().take(8).cloned().collect::<Vec<_>>())
                .unwrap_or_default();
            messages = crate::knowledge::messages(
                text(params, "question"),
                text(params, "schema"),
                "",
                &Value::Null,
            )
            .0;
            messages.as_array_mut().unwrap().extend([json!({"role":"assistant","content":script}),json!({"role":"user","content":format!("The user's mandatory changes are: {}. Keep these implemented while repairing the ENTIRE replacement script. Do not revert to the original behaviour. Validation reported: {}. Use the supported syntax reference; rejoin print-wrapped calculations and check string quoting if a closing block was swallowed by a calculation. Return only the complete corrected script, including unchanged sections. Mark unavoidable manual setup with a # TODO comment.",text(params,"question"),json!(issues))})]);
            let repaired =
                self.completion(&address, &key, &messages, &sections, 1, source_tokens)?;
            if !repaired.is_empty() {
                script = repaired;
                validation = validate(&script)?;
            }
        }
        self.check_cancel()?;
        self.update(
            "complete",
            "Draft generated. Review it in the workspace before copying native steps.",
            json!({"model":m["id"],"script":script,"validation":validation,"sections":sections}),
        );
        Ok(())
    }
    fn token_count(&self, address: &str, key: &str, content: &str) -> Result<usize, String> {
        self.check_cancel()?;
        let result: Value = Client::builder()
            .no_proxy()
            .timeout(Duration::from_secs(60))
            .build()
            .map_err(|e| e.to_string())?
            .post(format!("{address}/tokenize"))
            .bearer_auth(key)
            .json(&json!({"content":content,"add_special":true,"parse_special":true}))
            .send()
            .and_then(|r| r.error_for_status())
            .map_err(|e| format!("Could not measure script length: {e}"))?
            .json()
            .map_err(|e| e.to_string())?;
        result["tokens"]
            .as_array()
            .map(Vec::len)
            .ok_or("The AI engine returned an invalid token count.".into())
    }
    fn completion(
        &self,
        address: &str,
        key: &str,
        messages: &Value,
        sections: &[String],
        attempt: u8,
        source_tokens: usize,
    ) -> Result<String, String> {
        let client = Client::builder()
            .no_proxy()
            .timeout(Duration::from_secs(20 * 60))
            .build()
            .map_err(|e| e.to_string())?;
        self.check_cancel()?;
        let formatted: Value = client
            .post(format!("{address}/apply-template"))
            .bearer_auth(key)
            .json(&json!({"messages":messages,"chat_template_kwargs":{"enable_thinking":false}}))
            .send()
            .and_then(|r| r.error_for_status())
            .map_err(|e| format!("Could not check the model context: {e}"))?
            .json()
            .map_err(|e| e.to_string())?;
        let prompt = formatted["prompt"]
            .as_str()
            .ok_or("The AI engine could not measure the script context.")?;
        let input_tokens = self.token_count(address, key, prompt)?;
        let max_tokens = output_budget(input_tokens, source_tokens)?;
        let response=client.post(format!("{address}/v1/chat/completions")).bearer_auth(key).json(&json!({"messages":messages,"stream":true,"temperature":0.2,"max_tokens":max_tokens,"cache_prompt":false,"chat_template_kwargs":{"enable_thinking":false}})).send().and_then(|r|r.error_for_status()).map_err(|e|format!("Generation failed: {e}"))?;
        let mut generated = String::new();
        let mut last = Instant::now() - Duration::from_secs(1);
        let mut total = 0usize;
        let mut ended = false;
        let mut stopped = false;
        for line in BufReader::new(response).lines() {
            self.check_cancel()?;
            let line = line.map_err(|e| format!("Generation was interrupted: {e}"))?;
            total += line.len();
            if total > 8 * LIMIT {
                return Err("AI response exceeded the output limit.".into());
            }
            let Some(data) = line.strip_prefix("data: ") else {
                continue;
            };
            if data == "[DONE]" {
                ended = true;
                break;
            }
            let value: Value = serde_json::from_str(data)
                .map_err(|_| "The AI engine returned an invalid response.")?;
            if let Some(error) = value["error"]["message"].as_str() {
                return Err(error.into());
            }
            if let Some(token) = value["choices"][0]["delta"]["content"].as_str() {
                generated.push_str(token);
            }
            if value["choices"][0]["finish_reason"] == "length" {
                return Err("The model reached its output limit. The draft is incomplete and cannot be copied as a full replacement. Try a shorter source script or use another AI tool with a larger context.".into());
            }
            if let Some(reason) = value["choices"][0]["finish_reason"].as_str() {
                if reason != "stop" {
                    return Err(format!("The model did not finish a complete script ({reason}). Try generating again."));
                }
                stopped = true;
            }
            if last.elapsed() > Duration::from_millis(120) {
                self.update("generating",if attempt==0{"Generating a script with the bridge's reference…"}else{"Repairing the draft against the validator…"},json!({"script":crate::knowledge::clean_script(&generated),"sections":sections}));
                last = Instant::now();
            }
        }
        if !ended || !stopped {
            return Err("The AI response ended unexpectedly. Generate the draft again.".into());
        }
        Ok(crate::knowledge::clean_script(&generated))
    }
}

fn validate_attachment(attachment: &Value) -> Result<(), String> {
    if attachment.is_null() {
        return Ok(());
    }
    let name = text(attachment, "name");
    let content = text(attachment, "text");
    let pages = attachment["pages"].as_u64().unwrap_or(0);
    if name.is_empty()
        || name.len() > 1024
        || !name.to_lowercase().ends_with(".pdf")
        || !(1..=40).contains(&pages)
        || content.trim().is_empty()
        || content.chars().count() > 120000
        || content.len() > 480000
    {
        return Err(
            "Attach a readable script PDF with up to 40 pages and 120,000 characters.".into(),
        );
    }
    Ok(())
}
fn output_budget(input: usize, source: usize) -> Result<usize, String> {
    // Reserve enough output for the entire source plus amendments, never silently
    // truncate the attachment or ask the server to discard the start of the prompt.
    let required = (source.saturating_mul(3) / 2 + 1024).max(4096);
    let available = 32768usize.saturating_sub(input + 512).min(16384);
    if required > available {
        return Err("This script leaves too little room for a full replacement in the local model’s context. Attach a shorter script, remove duplicate workspace context, or use another AI tool with a larger context. No source text was shortened.".into());
    }
    Ok(available)
}

impl Drop for AiService {
    fn drop(&mut self) {
        self.cancel();
    }
}
fn physical_memory_gb() -> Option<f64> {
    #[cfg(target_os = "macos")]
    {
        use std::ffi::{c_char, c_void};
        unsafe extern "C" {
            fn sysctlbyname(
                name: *const c_char,
                old: *mut c_void,
                len: *mut usize,
                new: *mut c_void,
                newlen: usize,
            ) -> i32;
        }
        let mut bytes = 0u64;
        let mut len = 8usize;
        if unsafe {
            sysctlbyname(
                c"hw.memsize".as_ptr(),
                &mut bytes as *mut _ as *mut c_void,
                &mut len,
                std::ptr::null_mut(),
                0,
            )
        } == 0
        {
            return Some(bytes as f64 / 1_073_741_824.);
        }
    }
    #[cfg(windows)]
    {
        #[repr(C)]
        struct Memory {
            length: u32,
            load: u32,
            total: u64,
            available: u64,
            page: u64,
            available_page: u64,
            virtual_total: u64,
            available_virtual: u64,
            extended: u64,
        }
        #[link(name = "kernel32")]
        unsafe extern "system" {
            fn GlobalMemoryStatusEx(status: *mut Memory) -> i32;
        }
        let mut memory: Memory = unsafe { std::mem::zeroed() };
        memory.length = std::mem::size_of::<Memory>() as u32;
        if unsafe { GlobalMemoryStatusEx(&mut memory) } != 0 {
            return Some(memory.total as f64 / 1_073_741_824.);
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_invalid_pdf_context_and_reserves_a_complete_replacement() {
        assert!(validate_attachment(&Value::Null).is_ok());
        let pdf = json!({"name":"Script.pdf","pages":7,"text":"Set Variable [ $x ; Value: 1 ]"});
        assert!(validate_attachment(&pdf).is_ok());
        for invalid in [
            json!({}),
            json!({"name":"x.pdf","pages":41,"text":"script"}),
            json!({"name":"x.txt","pages":1,"text":"script"}),
            json!({"name":"x.pdf","pages":1,"text":" "}),
        ] {
            assert!(validate_attachment(&invalid).is_err());
        }
        assert_eq!(output_budget(12000, 8000).unwrap(), 16384);
        assert!(output_budget(24000, 8000).is_err());
        assert!(output_budget(4000, 12000).is_err());
        assert!(output_budget(32768, 0).is_err());
    }
    #[test]
    #[ignore = "Requires a private extracted PDF fixture and local Qwen inference"]
    fn real_model_amends_a_complete_pdf_script() {
        let fixture = std::env::var("BRIDGE_PDF_QA_JSON").expect(
            "Set BRIDGE_PDF_QA_JSON to an extracted attachment JSON outside source control",
        );
        let attachment: Value = serde_json::from_slice(&fs::read(fixture).unwrap()).unwrap();
        // Keep the original business requirements outside the public source too.
        let question = std::env::var("BRIDGE_PDF_QA_QUESTION")
            .expect("Set BRIDGE_PDF_QA_QUESTION to the private amendment request");
        let expected_condition = std::env::var("BRIDGE_PDF_QA_EXPECTED_CONDITION")
            .expect("Set BRIDGE_PDF_QA_EXPECTED_CONDITION to the required branch condition");
        assert!(!expected_condition.trim().is_empty());
        let id = std::env::var("BRIDGE_PDF_QA_MODEL").unwrap_or_else(|_| "9b".into());
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join(format!("../../.build/pdf-qa/inference-{id}"));
        let service = AiService::new(root.clone()).unwrap();
        let m = model(&id).unwrap();
        let source = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../.build/ai-qa-models")
            .join(text(&m, "filename"));
        let mut file = File::open(&source).unwrap();
        let mut hash = Sha256::new();
        let mut buffer = vec![0; LIMIT];
        loop {
            let n = file.read(&mut buffer).unwrap();
            if n == 0 {
                break;
            }
            hash.update(&buffer[..n]);
        }
        assert_eq!(format!("{:x}", hash.finalize()), text(&m, "sha256"));
        let destination = service.path(&m);
        if !destination.exists() {
            fs::hard_link(source, &destination).unwrap();
        }
        fs::write(
            destination.with_extension("verified.json"),
            serde_json::to_vec(
                &json!({"sha256":m["sha256"],"bytes":m["bytes"],"modified":modified(&destination)}),
            )
            .unwrap(),
        )
        .unwrap();
        let engine = Arc::new(Mutex::new(crate::worker::Worker::start().unwrap()));
        let worker = engine.clone();
        service.generate(json!({"model":id,"question":question,"schema":"Use the actual names in the attached original script.","existing":"","attachment":attachment}),move|text|worker.lock().unwrap().call(json!({"op":"compile","source":text,"templates":false}))).unwrap();
        let start = Instant::now();
        while service.busy.load(Ordering::SeqCst) {
            if start.elapsed() > Duration::from_secs(1500) {
                service.cancel();
                panic!("PDF generation timeout");
            }
            std::thread::sleep(Duration::from_millis(500));
        }
        let result = service.status();
        fs::write(
            root.join("result.json"),
            serde_json::to_vec_pretty(&result).unwrap(),
        )
        .unwrap();
        assert_eq!(
            result["operation"]["phase"], "complete",
            "{}",
            result["operation"]["message"]
        );
        let script = result["operation"]["script"].as_str().unwrap();
        assert!(
            script.lines().count() > 180,
            "Expected a whole replacement rather than a short example"
        );
        assert!(
            script.lines().any(|line| {
                let line = line.trim_start();
                (line.starts_with("If [") || line.starts_with("Else If ["))
                    && line.contains(&expected_condition)
            }),
            "A claimed change or an unused variable is not an implemented branch"
        );
        assert_eq!(
            result["operation"]["validation"]["canCopy"], true,
            "The full replacement still needs syntax correction"
        );
        // Keep this private result outside release/source archives for manual comparison.
        service.remove(&id).unwrap();
    }
    #[test]
    fn model_downloads_are_pinned_and_cannot_accept_arbitrary_paths() {
        for id in ["gemma4-e4b", "9b", "35b"] {
            let m = model(id).unwrap();
            assert_eq!(text(&m, "sha256").len(), 64);
            assert!(text(&m, "url").contains(text(&m, "revision")));
            assert!(bytes(&m) > 1_000_000_000);
            assert_eq!(m["license"], "Apache-2.0");
        }
        assert!(model("../../arbitrary-file").is_err());
    }
    #[test]
    fn prevents_overlapping_operations_and_allows_cancellation() {
        let root = std::env::temp_dir().join(format!("bridge-ai-{}", uuid::Uuid::new_v4()));
        let service = AiService::new(root.clone()).unwrap();
        assert!(service.begin().is_ok());
        assert!(service.begin().is_err());
        // Polling must not wait behind a process update, so the playground can
        // expose progress and Cancel even while a model is being prepared.
        {
            let _loading = service.server.lock().unwrap();
            assert_eq!(service.status()["busy"], true);
        }
        service.cancel();
        assert!(service.check_cancel().is_err());
        service.finish(Err("cancelled".into()));
        assert_eq!(service.status()["operation"]["phase"], "cancelled");
        assert_eq!(service.status()["busy"], false);
        drop(service);
        let _ = fs::remove_dir_all(root);
    }
    #[test]
    fn ready_receipts_require_matching_pinned_metadata() {
        let root = std::env::temp_dir().join(format!("bridge-ai-{}", uuid::Uuid::new_v4()));
        let service = AiService::new(root.clone()).unwrap();
        let m = json!({"filename":"test.gguf","bytes":4,"sha256":"expected"});
        let path = service.path(&m);
        fs::write(&path, b"GGUF").unwrap();
        assert!(!service.installed(&m));
        fs::write(
            path.with_extension("verified.json"),
            serde_json::to_vec(&json!({"bytes":4,"sha256":"expected","modified":modified(&path)}))
                .unwrap(),
        )
        .unwrap();
        assert!(service.installed(&m));
        fs::write(&path, b"truncated").unwrap();
        assert!(!service.installed(&m));
        drop(service);
        let _ = fs::remove_dir_all(root);
    }
    #[test]
    fn removal_clears_only_the_chosen_models_files_and_respects_active_jobs() {
        let root = std::env::temp_dir().join(format!("bridge-remove-{}", uuid::Uuid::new_v4()));
        let service = AiService::new(root.clone()).unwrap();
        let path = service.path(&model("9b").unwrap());
        let other = service.path(&model("35b").unwrap());
        fs::write(&path, b"downloaded model fixture").unwrap();
        fs::write(path.with_extension("part"), b"partial fixture").unwrap();
        fs::write(path.with_extension("verified.json"), b"{}").unwrap();
        fs::write(&other, b"keep this model").unwrap();
        service.begin().unwrap();
        assert!(service.remove("9b").is_err());
        assert!(path.exists());
        service.finish(Ok(()));
        assert!(service.remove("../../other").is_err());
        service.remove("9b").unwrap();
        assert!(!path.exists());
        assert!(!path.with_extension("part").exists());
        assert!(!path.with_extension("verified.json").exists());
        assert_eq!(fs::read(other).unwrap(), b"keep this model");
        assert_eq!(service.status()["busy"], false);
        service.remove("9b").unwrap(); // Removing again is safe.
        drop(service);
        let _ = fs::remove_dir_all(root);
    }
    #[test]
    #[ignore = "Requires a local loopback HTTP fixture"]
    fn download_resumes_and_rejects_a_bad_checksum() {
        use std::net::TcpListener;
        for valid in [true, false] {
            let root =
                std::env::temp_dir().join(format!("bridge-download-{}", uuid::Uuid::new_v4()));
            let service = AiService::new(root.clone()).unwrap();
            let data = b"GGUF test fixture";
            let listener = TcpListener::bind("127.0.0.1:0").unwrap();
            let port = listener.local_addr().unwrap().port();
            let sha = if valid {
                format!("{:x}", Sha256::digest(data))
            } else {
                "0".repeat(64)
            };
            let m = json!({"id":"test","filename":"test.gguf","bytes":data.len(),"sha256":sha,"url":format!("http://127.0.0.1:{port}/model"),"revision":"fixture"});
            fs::write(service.path(&m).with_extension("part"), &data[..4]).unwrap();
            let server = std::thread::spawn(move || {
                let (mut socket, _) = listener.accept().unwrap();
                let mut request = String::new();
                let mut reader = BufReader::new(socket.try_clone().unwrap());
                loop {
                    let mut line = String::new();
                    reader.read_line(&mut line).unwrap();
                    request.push_str(&line);
                    if line == "\r\n" {
                        break;
                    }
                }
                assert!(request.to_lowercase().contains("range: bytes=4-"));
                write!(socket,"HTTP/1.1 206 Partial Content\r\nContent-Length: {}\r\nContent-Range: bytes 4-{}/{}\r\nConnection: close\r\n\r\n",data.len()-4,data.len()-1,data.len()).unwrap();
                socket.write_all(&data[4..]).unwrap();
            });
            let result = service.download_model(&m);
            server.join().unwrap();
            if valid {
                assert!(result.is_ok(), "{result:?}");
                assert!(service.installed(&m));
                assert_eq!(fs::read(service.path(&m)).unwrap(), data);
            } else {
                assert!(result.is_err());
                assert!(!service.path(&m).exists());
                assert!(!service.path(&m).with_extension("part").exists());
            }
            drop(service);
            let _ = fs::remove_dir_all(root);
        }
    }
    #[test]
    #[ignore = "Requires the explicitly downloaded Qwen 9B fixture and local inference permissions"]
    fn real_model_generates_a_valid_native_script() {
        let id = std::env::var("BRIDGE_TEST_MODEL").unwrap_or_else(|_| "9b".into());
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../.build/ai-qa-data")
            .join(&id);
        let service = AiService::new(root.clone()).unwrap();
        let m = model(&id).unwrap();
        let source = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../.build/ai-qa-models")
            .join(text(&m, "filename"));
        let mut input = File::open(&source).expect("Download the pinned Qwen test fixture first");
        let mut sha = Sha256::new();
        let mut buf = vec![0; LIMIT];
        loop {
            let n = input.read(&mut buf).unwrap();
            if n == 0 {
                break;
            }
            sha.update(&buf[..n]);
        }
        assert_eq!(format!("{:x}", sha.finalize()), text(&m, "sha256"));
        let destination = service.path(&m);
        if !destination.exists() {
            fs::hard_link(&source, &destination).unwrap();
        }
        fs::write(
            destination.with_extension("verified.json"),
            serde_json::to_vec(
                &json!({"sha256":m["sha256"],"bytes":m["bytes"],"modified":modified(&destination)}),
            )
            .unwrap(),
        )
        .unwrap();
        let engine = Arc::new(Mutex::new(crate::worker::Worker::start().unwrap()));
        let worker = engine.clone();
        service.generate(json!({"model":id,"question":"Set a local variable $greeting to the text Hello. Show a custom dialog with title Greeting and message $greeting. Include an OK default button that does not commit the record. End the script with $greeting as its text result.","schema":"","existing":""}),move|text|worker.lock().unwrap().call(json!({"op":"compile","source":text,"templates":false}))).unwrap();
        let start = Instant::now();
        while service.busy.load(Ordering::SeqCst) {
            if start.elapsed() > Duration::from_secs(240) {
                service.cancel();
                panic!("Inference timeout: {}", service.status());
            }
            std::thread::sleep(Duration::from_millis(250));
        }
        let state = service.status();
        fs::write(
            root.join("generation-result.json"),
            serde_json::to_vec_pretty(&state).unwrap(),
        )
        .unwrap();
        assert_eq!(state["operation"]["phase"], "complete", "{state}");
        assert_eq!(state["operation"]["validation"]["canCopy"], true, "{state}");
        assert!(state["operation"]["script"]
            .as_str()
            .unwrap()
            .contains("Show Custom Dialog"));
        let worker = engine.clone();
        service.generate(json!({"model":id,"question":"Export the current found set to an XLSX file using $exportPath. Export Orders::OrderID, Orders::Total and Orders::Status in that order. Use field names as column headings and a worksheet named Orders. Do not show a dialog. Return only the script.","schema":"Orders::OrderID is a text ID. Orders::Total is a number. Orders::Status is text. $exportPath is already set to a valid FileMaker file path.","existing":""}),move|text|worker.lock().unwrap().call(json!({"op":"compile","source":text,"templates":false}))).unwrap();
        let start = Instant::now();
        while service.busy.load(Ordering::SeqCst) {
            if start.elapsed() > Duration::from_secs(240) {
                service.cancel();
                panic!("Export generation timeout: {}", service.status());
            }
            std::thread::sleep(Duration::from_millis(250));
        }
        let state = service.status();
        fs::write(
            root.join("export-generation-result.json"),
            serde_json::to_vec_pretty(&state).unwrap(),
        )
        .unwrap();
        assert_eq!(state["operation"]["phase"], "complete", "{state}");
        assert_eq!(state["operation"]["validation"]["canCopy"], true, "{state}");
        let draft = state["operation"]["script"].as_str().unwrap();
        assert!(
            draft.contains("Export Records")
                && draft.contains("Orders::OrderID")
                && draft.contains("Orders::Total")
                && draft.contains("Orders::Status")
        );
        service.remove(&id).unwrap();
        assert_eq!(service.status()["loadedModel"], Value::Null);
        assert!(!destination.exists());
        assert!(!destination.with_extension("verified.json").exists());
        assert!(source.is_file()); // The separate test fixture remains untouched.
    }
}
