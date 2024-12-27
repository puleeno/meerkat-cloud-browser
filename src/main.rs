use warp::Filter;

#[tokio::main]
async fn main() {
    // Định nghĩa một route phản hồi với tổng của hai số
    let sum_route = warp::path!("sum" / usize / usize)
        .map(|a: usize, b: usize| {
            let result = a + b;
            format!("Tổng của {} và {} là {}", a, b, result)
        });

    // Khởi động máy chủ web
    warp::serve(sum_route)
        .run(([127, 0, 0, 1], 3030))
        .await;
}