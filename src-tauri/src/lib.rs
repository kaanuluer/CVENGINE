use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::{Manager, RunEvent};

struct Engine(Mutex<Option<Child>>);

fn spawn_engine() -> Option<Child> {
    let engine_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../engine");
    Command::new("uv")
        .args([
            "run",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
        ])
        .current_dir(engine_dir)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .ok()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .setup(|app| {
            let child = spawn_engine();
            app.manage(Engine(Mutex::new(child)));
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("CVENGINE başlatılamadı");

    app.run(|app, event| {
        if let RunEvent::Exit = event {
            if let Some(state) = app.try_state::<Engine>() {
                if let Ok(mut guard) = state.0.lock() {
                    if let Some(mut child) = guard.take() {
                        let _ = child.kill();
                    }
                }
            }
        }
    });
}
