# Database Documentation – Splunk Blocker

File: `splunk_blocker.db` (SQLite 3)  
Managed by: `db_manager.py`

---

## Tổng quan

Database gồm **2 bảng**:

| Bảng | Mục đích |
|------|---------|
| `violations` | Ghi lại mỗi lần Splunk gửi webhook alert (1 alert = 1 row) |
| `ip_blocks` | Ghi lại mỗi lần hệ thống tạo lệnh block IP (kể cả đã hết hạn) |

Hai bảng liên kết với nhau qua trường `client_ip` (không có foreign key cứng để đơn giản hóa).

---

## Bảng `violations`

Lưu toàn bộ lịch sử alert từ Splunk. Không xóa row nào – đây là **audit log**.

```sql
CREATE TABLE IF NOT EXISTS violations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    client_ip  TEXT    NOT NULL,
    rule_name  TEXT    NOT NULL,
    timestamp  TEXT    NOT NULL,
    payload    TEXT
);
```

### Chi tiết từng cột

| Cột | Kiểu | Nullable | Mô tả |
|-----|------|----------|-------|
| `id` | INTEGER | NO | Primary key tự tăng |
| `client_ip` | TEXT | NO | Địa chỉ IP nguồn của request vi phạm (ví dụ: `"192.168.1.99"`) |
| `rule_name` | TEXT | NO | Tên Splunk alert rule đã trigger (ví dụ: `"Brute Force Login Attempt"`) |
| `timestamp` | TEXT | NO | Thời điểm nhận alert (ISO 8601 UTC, ví dụ: `"2026-07-02T15:30:00.000Z"`) |
| `payload` | TEXT | YES | Toàn bộ JSON payload từ Splunk (serialized string), dùng để audit hoặc debug |

### Ví dụ row

```
id=1, client_ip="10.0.0.1", rule_name="Brute Force Login Attempt",
timestamp="2026-07-02T16:03:00.000Z", payload="{...}"
```

### Queries thường dùng

```sql
-- Tất cả violations của một IP
SELECT * FROM violations WHERE client_ip = '192.168.1.99' ORDER BY timestamp DESC;

-- Violations trong 24h gần nhất
SELECT * FROM violations WHERE timestamp >= datetime('now', '-24 hours') ORDER BY timestamp DESC;

-- Số lượng violations theo IP
SELECT client_ip, COUNT(*) as total FROM violations GROUP BY client_ip ORDER BY total DESC;
```

---

## Bảng `ip_blocks`

Lưu lịch sử **lệnh block** đã phát ra. Một IP có thể có nhiều rows (nhiều lần bị block qua thời gian). Đây vừa là **trạng thái hiện tại** (nếu `block_end > now`) vừa là **lịch sử** (nếu `block_end <= now`).

```sql
CREATE TABLE IF NOT EXISTS ip_blocks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_ip       TEXT    NOT NULL,
    block_start     TEXT    NOT NULL,
    block_end       TEXT    NOT NULL,
    violation_count INTEGER NOT NULL,
    reason          TEXT    NOT NULL,
    status          TEXT    NOT NULL
);
```

### Chi tiết từng cột

| Cột | Kiểu | Nullable | Mô tả |
|-----|------|----------|-------|
| `id` | INTEGER | NO | Primary key tự tăng |
| `client_ip` | TEXT | NO | Địa chỉ IP bị block |
| `block_start` | TEXT | NO | Thời điểm bắt đầu block (ISO 8601 UTC) |
| `block_end` | TEXT | NO | Thời điểm hết hạn block (ISO 8601 UTC). Dùng để so sánh với `now` để biết block còn hiệu lực không |
| `violation_count` | INTEGER | NO | Tier của lần block này (1 = 5m, 2 = 30m, 3 = 7d). Phản ánh số lần bị block trong 7 ngày **tại thời điểm** block được tạo |
| `reason` | TEXT | NO | Mô tả lý do block, ví dụ: `"Triggered rule: 'Brute Force Login Attempt' (Violation #2)"` |
| `status` | TEXT | NO | `"ACTIVE"` khi mới tạo. Hiện tại chỉ dùng để seed/debug – trạng thái thực tế được tính động bằng cách so sánh `block_end > now` |

### Ví dụ rows

```
id=1, client_ip="192.168.1.99", block_start="2026-06-26T10:00:00Z",
      block_end="2026-06-26T10:05:00Z", violation_count=1,
      reason="Triggered rule: 'Credential Stuffing Alert' (Violation #1)", status="EXPIRED"

id=2, client_ip="192.168.1.99", block_start="2026-06-28T14:00:00Z",
      block_end="2026-06-28T14:30:00Z", violation_count=2,
      reason="Triggered rule: 'Credential Stuffing Alert' (Violation #2)", status="EXPIRED"

id=3, client_ip="192.168.1.99", block_start="2026-06-30T09:00:00Z",
      block_end="2026-07-07T09:00:00Z", violation_count=3,
      reason="Triggered rule: 'Credential Stuffing Alert' (Violation #3)", status="ACTIVE"
```

### Queries thường dùng

```sql
-- Các block đang còn hiệu lực (active) ngay lúc này
SELECT * FROM ip_blocks WHERE block_end > datetime('now') ORDER BY block_start DESC;

-- Lịch sử toàn bộ block của một IP
SELECT * FROM ip_blocks WHERE client_ip = '192.168.1.99' ORDER BY block_start DESC;

-- Số block trong 7 ngày gần nhất của một IP (dùng để tính tier tiếp theo)
SELECT COUNT(*) FROM ip_blocks
WHERE client_ip = '192.168.1.99'
  AND block_start >= datetime('now', '-7 days');

-- Tổng số lần bị block của mỗi IP
SELECT client_ip, COUNT(*) as total_blocks FROM ip_blocks GROUP BY client_ip ORDER BY total_blocks DESC;
```

---

## Logic xử lý block (Progressive Escalation)

### Quy trình khi nhận 1 webhook alert

```
Splunk gửi POST /webhook
        │
        ▼
1. Lưu vào bảng violations (luôn luôn)
        │
        ▼
2. Kiểm tra: IP có đang bị block không?
   (SELECT COUNT(*) FROM ip_blocks WHERE client_ip = ? AND block_end > now)
        │
   ┌────┴────┐
  CÓ        KHÔNG
   │          │
   └──────┐   ▼
   Bỏ qua  3. Đếm block trong 7 ngày gần nhất
          (count_recent_blocks)
                │
                ▼
          4. Xác định tier:
             recent_count = 0 → Tier 1 → block 5 phút
             recent_count = 1 → Tier 2 → block 30 phút
             recent_count ≥ 2 → Tier 3 → block 7 ngày
                │
                ▼
          5. INSERT vào ip_blocks với block_end = now + duration
```

### Bảng escalation

| Tier | Điều kiện (# block trong 7 ngày gần nhất) | Thời gian block |
|------|------------------------------------------|-----------------|
| 1 | 0 block gần đây | **5 phút** |
| 2 | 1 block gần đây | **30 phút** |
| 3 | ≥ 2 block gần đây | **7 ngày** |

### Quy tắc reset

> **Nếu một IP không bị block trong vòng 7 ngày, tier sẽ reset về 1.**

Ví dụ:
- IP `A` bị block lần 1 vào ngày 1 (tier 1 = 5m).
- IP `A` vi phạm lần nữa vào ngày **9** (> 7 ngày sau).
- `count_recent_blocks` trả về `0` → tier 1 lại → chỉ bị block 5 phút.

Điều này có nghĩa escalation không cộng dồn mãi mãi – chỉ tính trong **cửa sổ 7 ngày trượt**.

### Quy tắc không overlap

Nếu một IP **đang bị block** (block_end > now), hệ thống sẽ **không tạo block mới** dù có vi phạm đến. Vi phạm vẫn được ghi vào bảng `violations` nhưng không leo thang thêm cho đến khi block hiện tại hết hạn.

---

## Hàm trong `db_manager.py`

| Hàm | Mô tả |
|-----|-------|
| `init_db()` | Tạo hai bảng nếu chưa tồn tại |
| `record_violation(ip, rule, payload)` | Ghi vi phạm + tạo block nếu cần, trả về `block_info` hoặc `None` |
| `count_recent_blocks(ip, days=7)` | Đếm số block trong N ngày gần nhất (dùng để tính tier) |
| `get_active_blocks()` | Trả list các block đang còn hiệu lực (`block_end > now`) |
| `get_ip_block_history(ip)` | Trả toàn bộ lịch sử block của một IP cụ thể |
| `get_all_violations()` | Trả tất cả violations (dùng cho bảng Historical Alerts) |
| `get_total_block_count(ip)` | Đếm tổng số block ever của một IP |

---

## Ghi chú triển khai

- **Timestamp format**: Tất cả timestamp lưu dưới dạng chuỗi ISO 8601 UTC với suffix `Z`  
  (ví dụ: `"2026-07-02T15:30:00.000Z"`).  
  SQLite cho phép so sánh lexicographical trực tiếp với `datetime('now')` vì format nhất quán.

- **Không có index**: Ở quy mô nhỏ (< 100k rows) không cần. Nếu scale lên, thêm index:
  ```sql
  CREATE INDEX idx_ip_blocks_ip_end ON ip_blocks(client_ip, block_end);
  CREATE INDEX idx_violations_ip ON violations(client_ip);
  ```

- **Không có foreign key enforcement**: SQLite hỗ trợ FK nhưng phải bật thủ công (`PRAGMA foreign_keys = ON`). Hiện tại không dùng để đơn giản hóa.

- **File location**: `/home/tritc/Desktop/splunk-blocker/splunk_blocker.db` (hardcode trong `db_manager.py`).
