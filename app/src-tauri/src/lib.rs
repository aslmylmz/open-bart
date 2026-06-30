//! Tauri v2 shell for the offline BART instrument (SPEC §9, §10, §13).
//!
//! Thin by design: it spawns the Python scoring sidecar on a loopback port, hands
//! that port to the webview via the `get_sidecar_url` command, opens the window
//! that loads the Vite SPA, and kills the sidecar on exit. study.json load/save and
//! the kiosk toggle land in issue 12.

use std::io::{BufRead, BufReader};
use std::path::Path;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::Manager;

/// The spawned sidecar process plus the loopback URL it serves on. Held in Tauri's
/// managed state so `get_sidecar_url` can read the URL and the exit handler can kill
/// the child (no orphaned sidecar).
struct SidecarHandle {
    child: Mutex<Child>,
    base_url: String,
}

/// Parse the sidecar's `PORT=<n>` stdout handshake; `None` for any other line.
fn parse_port_line(line: &str) -> Option<u16> {
    line.trim().strip_prefix("PORT=").and_then(|s| s.trim().parse().ok())
}

/// The loopback base URL the sidecar serves on.
fn sidecar_base_url(port: u16) -> String {
    format!("http://127.0.0.1:{port}")
}

/// Dev: run the source sidecar from the env that has its deps (`BART_SIDECAR_PYTHON`,
/// default `python3`), with app/ on PYTHONPATH so `import sidecar` resolves.
#[cfg(debug_assertions)]
fn sidecar_command() -> Command {
    let python = std::env::var("BART_SIDECAR_PYTHON").unwrap_or_else(|_| "python3".to_string());
    let app_dir = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("app/src-tauri has a parent (app/)")
        .to_path_buf();
    let mut cmd = Command::new(python);
    cmd.args(["-m", "sidecar"]).env("PYTHONPATH", app_dir);
    cmd
}

/// Release: the PyInstaller binary bundled next to the app executable (externalBin).
#[cfg(not(debug_assertions))]
fn sidecar_command() -> Command {
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(Path::to_path_buf))
        .expect("the app executable has a parent directory");
    Command::new(exe_dir.join("bart-sidecar"))
}

/// Poll `/healthz` until the sidecar is serving, or give up after ~5s.
fn wait_for_healthz(base_url: &str) -> bool {
    let url = format!("{base_url}/healthz");
    for _ in 0..50 {
        if let Ok(resp) = ureq::get(&url).timeout(Duration::from_millis(500)).call() {
            if resp.status() == 200 {
                return true;
            }
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    false
}

/// Spawn the sidecar with its cwd set to a local sessions directory (so the default
/// study's `output_dir="."` lands there), read the PORT handshake, drain the rest of
/// stdout so a full pipe never stalls it (issue 09 lesson), and confirm it is healthy.
fn spawn_sidecar(app: &tauri::AppHandle) -> Result<SidecarHandle, Box<dyn std::error::Error>> {
    let sessions_dir = app.path().app_local_data_dir()?.join("sessions");
    std::fs::create_dir_all(&sessions_dir)?;

    let mut child = sidecar_command()
        .current_dir(&sessions_dir)
        // Hold the child's stdin open as a liveness pipe: if this process dies
        // (hard kill, dev Ctrl-C), the OS closes it and the sidecar's watchdog sees
        // EOF and exits — the no-orphan backstop to the graceful kill on RunEvent::Exit.
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .env("BART_SIDECAR_WATCH_PARENT", "1")
        .spawn()?;

    let stdout = child.stdout.take().ok_or("sidecar stdout was not captured")?;
    let mut reader = BufReader::new(stdout);

    let mut port: Option<u16> = None;
    let deadline = Instant::now() + Duration::from_secs(60);
    let mut line = String::new();
    while Instant::now() < deadline {
        line.clear();
        if reader.read_line(&mut line)? == 0 {
            break; // EOF: the sidecar exited before announcing a port
        }
        if let Some(p) = parse_port_line(&line) {
            port = Some(p);
            break;
        }
    }
    let port = match port {
        Some(p) => p,
        None => {
            let _ = child.kill();
            return Err("sidecar did not announce a PORT".into());
        }
    };

    // Keep draining stdout so a full pipe buffer never blocks the sidecar.
    std::thread::spawn(move || {
        let mut sink = String::new();
        while reader.read_line(&mut sink).unwrap_or(0) > 0 {
            sink.clear();
        }
    });

    let base_url = sidecar_base_url(port);
    if !wait_for_healthz(&base_url) {
        let _ = child.kill();
        return Err("sidecar did not pass its /healthz check".into());
    }
    eprintln!(
        "[bart] sidecar ready at {base_url}; writing sessions to {}",
        sessions_dir.display()
    );
    Ok(SidecarHandle { child: Mutex::new(child), base_url })
}

/// Hand the sidecar's loopback URL to the webview at startup (SPEC §10 port handoff).
#[tauri::command]
fn get_sidecar_url(state: tauri::State<'_, SidecarHandle>) -> String {
    state.base_url.clone()
}

/// Read study.json from a user-chosen path (issue 12). The native dialog supplies the
/// path, so the user's explicit choice is the authorization — std::fs here keeps the
/// fs-plugin capability scope (and a broad allowlist) out of it.
#[tauri::command]
fn read_study_file(path: String) -> Result<String, String> {
    std::fs::read_to_string(&path).map_err(|e| e.to_string())
}

/// Write study.json to a user-chosen path (see `read_study_file` on authorization).
#[tauri::command]
fn write_study_file(path: String, content: String) -> Result<(), String> {
    std::fs::write(&path, content).map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .setup(|app| {
            let handle = spawn_sidecar(app.handle())?;
            app.manage(handle);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_sidecar_url,
            read_study_file,
            write_study_file
        ])
        .build(tauri::generate_context!())
        .expect("error while building the BART desktop shell")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                if let Some(handle) = app_handle.try_state::<SidecarHandle>() {
                    let _ = handle.child.lock().unwrap().kill();
                }
            }
        });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_the_port_announcement() {
        assert_eq!(parse_port_line("PORT=51234\n"), Some(51234));
        assert_eq!(parse_port_line("  PORT=8 \n"), Some(8));
    }

    #[test]
    fn ignores_non_port_lines() {
        assert_eq!(parse_port_line("INFO: started\n"), None);
        assert_eq!(parse_port_line("PORT=not-a-number\n"), None);
    }

    #[test]
    fn base_url_targets_loopback() {
        assert_eq!(sidecar_base_url(5000), "http://127.0.0.1:5000");
    }

    #[test]
    fn study_file_round_trips() {
        let path = std::env::temp_dir()
            .join(format!("bart-study-{}.json", std::process::id()))
            .to_string_lossy()
            .into_owned();
        write_study_file(path.clone(), "{\"title\":\"t\"}".into()).unwrap();
        assert_eq!(read_study_file(path.clone()).unwrap(), "{\"title\":\"t\"}");
        let _ = std::fs::remove_file(path);
    }
}
