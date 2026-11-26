# Deploy không cần thẻ: Cloudflare Workers

WebTranslate AI có bản Worker độc lập ở `worker/`. Dùng Cloudflare Workers Free; bạn không cần Render, Docker, API key LibreTranslate, hoặc thẻ thanh toán.

## Deploy bằng dashboard (không cần cài gì)

1. Tạo tài khoản Cloudflare: https://dash.cloudflare.com/sign-up
2. Dashboard → **Workers & Pages** → **Create** → **Worker** (hoặc Create application → Worker).
3. Chọn **Deploy Hello World** để tạo Worker đầu tiên.
4. Vào Worker → **Edit code**.
5. Mở file `worker/index.js` trong repository GitHub này, copy toàn bộ nội dung và dán vào editor Cloudflare.
6. Nhấn **Save and Deploy**.
7. Mở URL Worker dạng `https://<worker-name>.<account>.workers.dev`. Trang dịch sẽ xuất hiện.
8. Health check: thêm `/health`, kết quả JSON status ok.

Không nhập `LIBRETRANSLATE_URL` hay `LIBRETRANSLATE_KEY`; dịch mặc định qua MyMemory anonymous, có hạn mức và có thể bị rate limit. Không nhập thẻ / nâng cấp plan.

## Deploy với Wrangler (tuỳ chọn)

Cần Node.js/npm cài trên máy:

```bash
cd worker
npx wrangler deploy
```

## Tính năng và hạn chế

- Giao diện tiếng Việt, chọn ngôn ngữ nguồn/đích.
- Dịch text và một số thuộc tính alt/title/placeholder/aria-label.
- HTMLRewriter streaming; cố giữ HTML markup, CSS, hình ảnh; thêm base URL cho tài nguyên tương đối.
- Link nội bộ quay lại endpoint dịch với lựa chọn ngôn ngữ.
- Bỏ script, iframe, object, embed; trang cần JavaScript gốc có thể bị hỏng.
- Giới hạn HTML 1.5 MB; giới hạn dịch 35 text chunks và 15.000 ký tự.
- Chặn localhost, hostname local, credentials, cổng ngoài 80/443, một số IPv4 private/reserved. Worker proxy public có rủi ro SSRF còn lại; không sử dụng cho website private/authenticated.
- MyMemory anonymous có quota, translation có thể trả text gốc khi quota hoặc provider lỗi.
- Chưa có cache bền vững, chưa dịch CSS background-image hoặc đầy đủ nội dung động.

## Mã nguồn

Worker: https://github.com/tranmaocat-jpg/webtranslate-ai/tree/main/worker
