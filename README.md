# 🦫 Meerkat Cloud Browser - Tài liệu Kiến trúc Hệ thống

## 📌 Giới thiệu
**Meerkat Cloud Browser** là một hệ thống crawler phiên bản mây chủ, sử dụng Firefox ESR kèm geckordp để thu thập dữ liệu HTTP response theo request từ client (Laravel/WordPress hoặc App bên ngoài). Meerkat cho phép các user tạo project, gán crawler và parser theo rule tự định nghĩa, và nhận kết quả về qua webhook/API.

## 🧩 Kiến trúc tổng thể
```
Client App
  |                
  |--> Meerkat RPC Gateway (Flask)
        |--> Task Queue (RQ/Redis)
        |--> Crawler Node (Firefox + geckordp)
        |--> DOM Parser (BeautifulSoup4 + Rule Engine)
        |--> Result -> PostgreSQL (JSONB)
        |--> Webhook or API callback
        |--> Cold Export: S3/MinIO
        |--> Analytics Push: ClickHouse/BigQuery (optional)
```

## 🔧 Tính năng chính
### 📁 Quản lý Project
- Mỗi user sở hữu nhiều project
- Mỗi project có nhiều data source
- Cấu hình rule parsing, URL, crawl mode, mapping fields

### 🕷️ Crawler Engine
- Firefox ESR + geckordp headless
- Quản lý session/login theo profile user
- Tự scale crawler instance theo project/job
- Cho phép login trước khi crawl (Facebook, Zalo...)

### 🧠 Parser Rule
- Rule dựa trên:
  - HTML (DOM, CSS selector)
  - JSON, CSV
  - URL format, regex
- GUI DOM Picker: tích hợp `@medv/finder` cho selector ngắn
- Tự động sinh rule và preview trực quan

### 🔌 Plugin System (Scripted Parser)
- User nhúng script RestrictedPython theo project
- Sandbox execution, track time + memory + exception
- Warning & chặn plugin vượt ngưỡng (tuỳ theo plan)

### 🧵 Job Engine
- Dựa trên Redis Queue (RQ)
- Multi-thread/task per project
- Retry, backoff, dedup URL, TTL
- Gửi webhook khi hoàn tất hoặc có lỗi

### 🗃️ Lưu trữ dữ liệu
- PostgreSQL với JSONB
- Cold Export: CSV/JSONL → S3/MinIO
- Analytics: ClickHouse / BigQuery

### 📊 Dashboard Admin/User
- Realtime job monitor (WebSocket)
- Job retry / log / preview
- DOM Mapping GUI + plugin editor
- Credit usage & log transaction
- Lịch sử export / webhook event

---

## 🧭 Module Diagram: Parser Engine
```plantuml
@startuml
package "Parser Engine" {
  [Parser Core] --> [Rule Matcher]
  [Parser Core] --> [Plugin Runner]
  [Parser Core] --> [Field Mapper]
  [Rule Matcher] --> [DOM Selector]
  [Plugin Runner] --> [Sandbox Executor]
  [Parser Core] --> [Result Validator]
  [Result Validator] --> [Error Logger]
}
@enduml
```

### 🔄 Flow Diagram: Parser Engine
```plantuml
@startuml
start
:Receive raw response;
:Detect rule type (HTML/JSON);
if (HTML) then (yes)
  :Use Rule Matcher -> DOM Selector;
else
  :Parse JSON/CSV with field_map;
endif
:Run Plugin (if exists);
:Field Mapping;
:Validate result;
if (error) then (yes)
  :Log to Error Logger;
endif
:Save structured data;
stop
@enduml
```

---

## 🕒 Module Diagram: Scheduler System
```plantuml
@startuml
package "Scheduler" {
  [Schedule Manager] --> [Project Config Reader]
  [Schedule Manager] --> [Job Generator]
  [Job Generator] --> [Redis Queue]
  [Schedule Manager] --> [Execution Calendar]
  [Execution Calendar] --> [Interval Checker]
}
@enduml
```

### 🔄 Flow Diagram: Scheduler System
```plantuml
@startuml
start
:Scan all projects with schedules;
:Check Execution Calendar;
if (time matches interval) then (yes)
  :Read Project Config;
  :Generate crawl job;
  :Push to Redis Queue;
else
  :Skip;
endif
stop
@enduml
```

---

## 📡 Module Diagram: Monitor & Metrics
```plantuml
@startuml
package "Monitoring" {
  [Job Tracker] --> [Status DB Logger]
  [Job Tracker] --> [WebSocket Broadcaster]
  [Job Tracker] --> [Alert Dispatcher]
  [Alert Dispatcher] --> [Webhook Notifier]
  [Job Tracker] --> [Performance Evaluator]
  [Performance Evaluator] --> [Threshold Ruleset]
  [Threshold Ruleset] --> [User Plan Limit]
}
@enduml
```

### 🔄 Flow Diagram: Monitor & Metrics
```plantuml
@startuml
start
:Job execution starts;
:Track status + metrics;
:Log status to DB;
:Broadcast to WebSocket clients;
:Evaluate performance thresholds;
if (violation) then (yes)
  :Dispatch alert (Webhook + UI);
endif
stop
@enduml
```

---

## 💳 Flow Diagram: Credit & Billing
```plantuml
@startuml
start
:User triggers paid action (e.g. crawl job);
:Check user credit balance;
if (enough credit) then (yes)
  :Deduct credits based on action type;
  :Log transaction (action, credits, timestamp);
  :Allow action to proceed;
else (no)
  :Reject action;
  :Notify user: insufficient credit;
endif
stop
@enduml
```

## 📤 Flow Diagram: Export Job Pipeline
```plantuml
@startuml
start
:User requests export (CSV/JSONL);
:Create export job entry in DB;
:Push job to Export Queue;
:Worker pulls export job;
:Fetch parsed data from DB;
:Generate file in desired format;
:Upload to S3/MinIO bucket;
:Update job status to completed;
:Notify user via dashboard / webhook;
stop
@enduml
```

## 🔐 Flow Diagram: Security Audit Trail
```plantuml
@startuml
start
:User performs sensitive action (e.g. script upload);
:Capture event metadata (user_id, ip, time);
:Validate user role + permissions;
if (valid) then (yes)
  :Allow action;
else (no)
  :Block and notify admin;
endif
:Log action to audit log table;
:Monitor audit log for anomaly patterns;
:Trigger alert if threshold breached;
stop
@enduml
```

## 🛡️ Flow Diagram: RBAC Access Flow
```plantuml
@startuml
start
:User requests resource (e.g. view job, edit rule);
:Get user_id from session/token;
:Fetch user's role in project;
:Lookup permission matrix for requested action;
if (permission granted?) then (yes)
  :Allow action and continue;
else (no)
  :Deny action and return 403;
  :Log permission denial;
endif
stop
@enduml
```

---

*Đây là tài liệu kỹ thuật hợp nhất, phục vụ export PDF/HTML hoặc chia sẻ nội bộ nhóm dev.*
