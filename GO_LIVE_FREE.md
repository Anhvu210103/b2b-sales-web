# Bản cá nhân: Render Free + Neon Free

Đã có cấu hình deploy, chưa có website public. Bạn cần sở hữu tài khoản hosting
và nhập credentials trong bảng cài đặt của nhà cung cấp; không gửi chúng vào chat.

Mục tiêu là giao diện + khách hàng + deal + Kanban + ghi chú. Bản này không tạo
VPS, worker, Redis, ổ đĩa trả phí hay tên miền riêng. Dùng tên miền HTTPS mà Render
cấp. Không cài Chromium, AI hoặc scraper trong runtime này.

## 1. Tạo database

Đăng ký tại https://neon.com và chọn gói **Free**. Tạo một project PostgreSQL,
chọn vùng gần dịch vụ web, rồi lấy connection string PostgreSQL **Direct** (không dùng pooler) từ Connect.
Giữ tham số SSL; app sẽ xác minh certificate và hostname khi kết nối.
Database nằm ở Neon nên không bị mất khi Render ngủ hoặc thay máy.

## 2. Đưa code lên GitHub

Bản triển khai dùng branch `codex/personal-free-deploy-20261014`.
Chọn branch này khi kết nối repository với Render; Render không nhìn thấy code
chỉ nằm trên máy phát triển.
Không commit `.env`, backup hay credentials. Có thể dùng một branch riêng cho bản
cá nhân và chọn branch đó khi tạo Blueprint.

## 3. Tạo website

Đăng ký tại https://render.com, kết nối GitHub, chọn **New → Blueprint**, rồi chọn
repository `Anhvu210103/b2b-sales-web` và branch chứa các thay đổi.
Render đọc `render.yaml`; kiểm tra dịch vụ `chatask-personal` có plan **Free**.
Không thêm database hoặc dịch vụ trả phí trong Render.

Điền các biến riêng trong cài đặt Render:

| Biến | Giá trị |
| --- | --- |
| `DATABASE_URL` | Connection string từ Neon, gồm SSL |
| `B2B_BOOTSTRAP_EMAIL` | Email đăng nhập của bạn |
| `B2B_BOOTSTRAP_PASSWORD` | Mật khẩu riêng, ít nhất 12 ký tự, tối đa 72 byte UTF-8 |

`SECRET_KEY` được sinh tự động; không đổi key sau mỗi deploy. App tự tạo tài khoản
quản trị đầu tiên khi database chưa có admin, không reset tài khoản khi restart.
Sau khi đăng nhập thành công, xóa **cả hai** biến `B2B_BOOTSTRAP_*` rồi redeploy.
Tài khoản vẫn nằm trong database. Không có tài khoản/mật khẩu mặc định.

Sau deploy, mở URL HTTPS được Render cấp, đăng nhập, tạo một khách hàng, tạo deal,
đổi giai đoạn và lưu ghi chú. Reload rồi kiểm tra dữ liệu vẫn còn.

## Giới hạn của bản free

- App có thể ngủ khi không dùng; lần mở lại có thể chậm.
- Có quota tài nguyên và thời gian chạy; không dùng dịch vụ chống ngủ để né quota.
- File trong `/tmp` là tạm thời. Bản CRM này không dùng nó làm nơi lưu dữ liệu lâu dài.
- Email, AI, scraping và tác vụ nền chưa được bật.
- Điều kiện Free phải xác nhận ở trang đăng ký/checkout. Môi trường hiện tại chặn
  đọc tài liệu giá Render/Neon; chưa xác minh điều kiện, quota hay yêu cầu thẻ hiện tại.
  Nếu chỉ có phương án trả phí, dừng trước khi xác nhận vì mục tiêu là 0 đồng.

## Backup đơn giản

Mỗi tuần và trước khi nâng cấp, trên máy tính có Docker, đặt `DATABASE_URL` qua
biến môi trường riêng rồi chạy `bash deploy/backup.sh`.
Script tạo dump có quyền đọc riêng, kiểm tra danh sách nội dung, và không ghi
credentials vào file cấu hình. Cất dump ngoài repository. Backup này cần bạn chạy;
chưa có backup tự động được cài đặt.

Để phục hồi, tạo database mới và dùng `pg_restore` với dump đã lưu, sau đó đổi
`DATABASE_URL` của Render sang database mới. Không phục hồi đè database đang dùng
khi chưa có bản backup và kế hoạch cụ thể.
