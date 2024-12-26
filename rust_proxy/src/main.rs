mod python_server;

use axum::{
    routing::{get, post},
    Router,
    http::StatusCode,
    response::IntoResponse,
    Json,
    extract::State,
};
use python_server::PythonServer;
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use std::sync::Arc;
use tower_http::cors::{CorsLayer, Any};
use reqwest::Client;
use std::path::PathBuf;

// Shared state
#[derive(Clone)]
struct AppState {
    client: Client,
    python_api_url: String,
}

// Request/Response structures
#[derive(Debug, Serialize, Deserialize)]
struct UrlRequest {
    url: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct JavaScriptRequest {
    script: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct ApiResponse {
    status: String,
}

// Handler functions
async fn start_browser(
    State(state): State<Arc<AppState>>
) -> impl IntoResponse {
    match state.client.post(format!("{}/browser/start", state.python_api_url))
        .send()
        .await {
            Ok(response) => {
                let status = response.status();
                if status.is_success() {
                    (StatusCode::OK, Json(response.json::<ApiResponse>().await.unwrap()))
                } else {
                    (StatusCode::INTERNAL_SERVER_ERROR, Json(ApiResponse {
                        status: "Failed to start browser".to_string()
                    }))
                }
            },
            Err(_) => (StatusCode::INTERNAL_SERVER_ERROR, Json(ApiResponse {
                status: "Failed to connect to Python API".to_string()
            }))
        }
}

async fn navigate_browser(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<UrlRequest>
) -> impl IntoResponse {
    match state.client.post(format!("{}/browser/navigate", state.python_api_url))
        .json(&payload)
        .send()
        .await {
            Ok(response) => {
                let status = response.status();
                if status.is_success() {
                    (StatusCode::OK, Json(response.json::<ApiResponse>().await.unwrap()))
                } else {
                    (StatusCode::INTERNAL_SERVER_ERROR, Json(ApiResponse {
                        status: "Failed to navigate".to_string()
                    }))
                }
            },
            Err(_) => (StatusCode::INTERNAL_SERVER_ERROR, Json(ApiResponse {
                status: "Failed to connect to Python API".to_string()
            }))
        }
}

async fn stop_browser(
    State(state): State<Arc<AppState>>
) -> impl IntoResponse {
    match state.client.post(format!("{}/browser/stop", state.python_api_url))
        .send()
        .await {
            Ok(response) => {
                let status = response.status();
                if status.is_success() {
                    (StatusCode::OK, Json(response.json::<ApiResponse>().await.unwrap()))
                } else {
                    (StatusCode::INTERNAL_SERVER_ERROR, Json(ApiResponse {
                        status: "Failed to stop browser".to_string()
                    }))
                }
            },
            Err(_) => (StatusCode::INTERNAL_SERVER_ERROR, Json(ApiResponse {
                status: "Failed to connect to Python API".to_string()
            }))
        }
}

async fn take_screenshot(
    State(state): State<Arc<AppState>>
) -> impl IntoResponse {
    match state.client.get(format!("{}/browser/screenshot", state.python_api_url))
        .send()
        .await {
            Ok(response) => {
                let status = response.status();
                if status.is_success() {
                    (StatusCode::OK, Json(response.json::<ApiResponse>().await.unwrap()))
                } else {
                    (StatusCode::INTERNAL_SERVER_ERROR, Json(ApiResponse {
                        status: "Failed to take screenshot".to_string()
                    }))
                }
            },
            Err(_) => (StatusCode::INTERNAL_SERVER_ERROR, Json(ApiResponse {
                status: "Failed to connect to Python API".to_string()
            }))
        }
}

async fn execute_javascript(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<JavaScriptRequest>
) -> impl IntoResponse {
    match state.client.post(format!("{}/browser/execute", state.python_api_url))
        .json(&payload)
        .send()
        .await {
            Ok(response) => {
                let status = response.status();
                if status.is_success() {
                    (StatusCode::OK, Json(response.json::<ApiResponse>().await.unwrap()))
                } else {
                    (StatusCode::INTERNAL_SERVER_ERROR, Json(ApiResponse {
                        status: "Failed to execute JavaScript".to_string()
                    }))
                }
            },
            Err(_) => (StatusCode::INTERNAL_SERVER_ERROR, Json(ApiResponse {
                status: "Failed to connect to Python API".to_string()
            }))
        }
}

#[tokio::main]
async fn main() {
    // Initialize tracing
    tracing_subscriber::fmt::init();

    // Start Python FastAPI server
    let python_server = PythonServer::new(
        PathBuf::from("../python_api/app/main.py"),
        8000
    );

    // Run Python server in a separate task
    tokio::spawn(async move {
        if let Err(e) = python_server.run().await {
            eprintln!("Python server error: {}", e);
        }
    });

    // Give Python server time to start
    tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;

    // Shared state
    let state = Arc::new(AppState {
        client: Client::new(),
        python_api_url: "http://localhost:8000".to_string(),
    });

    // CORS configuration
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    // Router with routes
    let app = Router::new()
        .route("/browser/start", post(start_browser))
        .route("/browser/navigate", post(navigate_browser))
        .route("/browser/stop", post(stop_browser))
        .route("/browser/screenshot", get(take_screenshot))
        .route("/browser/execute", post(execute_javascript))
        .layer(cors)
        .with_state(state);

    // Bind and serve
    let addr = SocketAddr::from(([127, 0, 0, 1], 3000));
    tracing::info!("Proxy server running on http://{}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}