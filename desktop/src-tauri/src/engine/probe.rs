//! Engine Identity Probe — PORT_FREE | PLANSEED_ENGINE | FOREIGN_SERVICE。

use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream, ToSocketAddrs};
use std::process::Child;
use std::thread;
use std::time::{Duration, Instant};

use serde_json::Value;

/// 与 backend/routes/health.py 对齐。
pub const EXPECTED_SERVICE: &str = "planseed";
pub const EXPECTED_API_VERSION: &str = "1";
pub const MAX_SPAWN_ATTEMPTS: u32 = 5;
pub const ATTEMPT_HEALTH_TIMEOUT: Duration = Duration::from_secs(12);

/// 端口身份三态。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PortIdentity {
    PortFree,
    PlanseedEngine,
    ForeignService,
}

pub fn engine_host() -> String {
    std::env::var("PLANSEED_HOST").unwrap_or_else(|_| "127.0.0.1".into())
}

pub fn preferred_port() -> u16 {
    std::env::var("PLANSEED_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8787)
}

fn tcp_connectable(host: &str, port: u16) -> bool {
    let addr = format!("{host}:{port}");
    let Ok(mut addrs) = addr.to_socket_addrs() else {
        return false;
    };
    let Some(sock) = addrs.next() else {
        return false;
    };
    TcpStream::connect_timeout(&sock, Duration::from_millis(200)).is_ok()
}

fn http_get_health_body(host: &str, port: u16) -> Option<String> {
    let addr = format!("{host}:{port}");
    let mut addrs = addr.to_socket_addrs().ok()?;
    let sock_addr = addrs.next()?;
    let mut stream = TcpStream::connect_timeout(&sock_addr, Duration::from_millis(400)).ok()?;
    let _ = stream.set_read_timeout(Some(Duration::from_millis(800)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(800)));

    let req = format!(
        "GET /api/health HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\nAccept: application/json\r\n\r\n"
    );
    stream.write_all(req.as_bytes()).ok()?;
    let mut buf = Vec::new();
    let _ = stream.read_to_end(&mut buf);
    let text = String::from_utf8_lossy(&buf);
    let ok_status = text.starts_with("HTTP/1.1 200") || text.starts_with("HTTP/1.0 200");
    if !ok_status {
        return None;
    }
    let body = text.split("\r\n\r\n").nth(1)?.trim();
    if body.is_empty() {
        return None;
    }
    Some(body.to_string())
}

pub fn is_planseed_health_json(body: &str) -> bool {
    let Ok(v) = serde_json::from_str::<Value>(body) else {
        return false;
    };
    let ok = v.get("ok").and_then(|x| x.as_bool()) == Some(true);
    let service = v.get("service").and_then(|x| x.as_str()) == Some(EXPECTED_SERVICE);
    let api = v.get("api_version").and_then(|x| x.as_str()) == Some(EXPECTED_API_VERSION);
    let engine = v
        .get("engine_version")
        .and_then(|x| x.as_str())
        .map(|s| !s.is_empty())
        .unwrap_or(false);
    ok && service && api && engine
}

/// 应用级探针：PORT_FREE | PLANSEED_ENGINE | FOREIGN_SERVICE
pub fn probe_engine(host: &str, port: u16) -> PortIdentity {
    if !tcp_connectable(host, port) {
        return PortIdentity::PortFree;
    }
    match http_get_health_body(host, port) {
        Some(body) if is_planseed_health_json(&body) => PortIdentity::PlanseedEngine,
        _ => PortIdentity::ForeignService,
    }
}

pub fn suggest_port(host: &str, preferred: u16, attempt: u32) -> u16 {
    if attempt == 0 {
        match probe_engine(host, preferred) {
            PortIdentity::PortFree => preferred,
            PortIdentity::ForeignService => {
                log::warn!("preferred {preferred} is FOREIGN_SERVICE; suggesting another port");
                suggest_ephemeral(host).unwrap_or(preferred.wrapping_add(1))
            }
            PortIdentity::PlanseedEngine => preferred,
        }
    } else {
        suggest_ephemeral(host).unwrap_or(preferred.wrapping_add(attempt as u16))
    }
}

fn suggest_ephemeral(host: &str) -> Option<u16> {
    TcpListener::bind((host, 0))
        .ok()
        .and_then(|l| l.local_addr().ok())
        .map(|a| a.port())
}

pub fn wait_for_engine(host: &str, port: u16, child: &mut Child, timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        match child.try_wait() {
            Ok(Some(status)) => {
                log::warn!("backend exited before healthy (status={status})");
                return false;
            }
            Err(e) => {
                log::warn!("backend wait error: {e}");
                return false;
            }
            Ok(None) => {}
        }
        if probe_engine(host, port) == PortIdentity::PlanseedEngine {
            return true;
        }
        thread::sleep(Duration::from_millis(250));
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_non_planseed_json() {
        assert!(!is_planseed_health_json(r#"{"ok":true}"#));
        assert!(!is_planseed_health_json(
            r#"{"ok":true,"service":"other","api_version":"1","engine_version":"1"}"#
        ));
        assert!(is_planseed_health_json(
            r#"{"ok":true,"service":"planseed","api_version":"1","engine_version":"0.1.0"}"#
        ));
    }
}
