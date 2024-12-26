use std::process::Stdio;
use tokio::process::Command;
use std::path::PathBuf;

pub struct PythonServer {
    app_path: PathBuf,
    port: u16,
}

impl PythonServer {
    pub fn new(app_path: PathBuf, port: u16) -> Self {
        Self { app_path, port }
    }

    pub async fn run(&self) -> Result<(), Box<dyn std::error::Error>> {
        let status = Command::new("hypercorn")
            .arg("--bind")
            .arg(format!("0.0.0.0:{}", self.port))
            .arg("--workers")
            .arg("4")
            .arg(format!("{}:app", self.app_path.to_str().unwrap()))
            .current_dir(self.app_path.parent().unwrap())
            .stdout(Stdio::inherit())
            .stderr(Stdio::inherit())
            .status()
            .await?;

        if !status.success() {
            return Err("Python server failed to start".into());
        }

        Ok(())
    }
}