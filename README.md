# yoloDetectPeople-DeterminHotSpace-group5

![Project Cover](Docs/demo_cover.jpg)

## 📖 專案簡介 (Introduction)

本專案是一套結合 **電腦視覺（Computer Vision）**、**雲端服務（AWS）** 與 **物聯網（IoT）** 的 **AIoT 即時互動系統**。  
系統透過電腦攝影機即時擷取畫面，將畫面劃分為 **九宮格**，並偵測是否有「人物」出現在各區域中。

目前開發階段以 **手掌作為人物替代目標**，只要在任一格子中偵測到手掌，即視為該格子有人出現，並即時觸發對應的燈泡亮起。

此系統可用於：
- 人流熱區分析
- 展覽互動裝置
- 智慧照明
- 空間使用行為分析

---

## 🚀 核心功能 (Key Features)

- **九宮格畫面分割**
  - 將攝影機即時畫面切割為 3×3 共 9 個區域
  - 每個區域獨立進行人物（手掌）存在判斷

- **即時人物（手掌）偵測**
  - 使用影像辨識技術偵測畫面中是否出現手掌
  - 手掌作為人物存在的替代條件（Prototype 階段）

- **雲端訊息傳遞（AWS + MQTT）**
  - 偵測結果即時傳送至 AWS
  - 透過 MQTT 協定發布對應九宮格訊號

- **ESP8266 燈泡控制**
  - ESP8266 訂閱 MQTT Topic
  - 控制外接的 9 顆燈泡
  - 對應九宮格即時亮燈

- **Web 即時監控 Dashboard**
  - 顯示每顆燈泡目前狀態（ON / OFF）
  - 統計每個格子「開燈次數」
  - 累積「亮燈超過 10 秒」的次數
  - 用於判斷人流 **熱區（Hot Zone）**

---

## 🧠 系統流程概觀 (System Flow)

1. 攝影機擷取即時畫面
2. 畫面切割為九宮格
3. 逐格進行手掌偵測
4. 偵測成功 → 傳送結果至 AWS
5. AWS 透過 MQTT 發布訊息
6. ESP8266 接收訊號 → 對應燈泡亮起
7. Web Dashboard 即時更新燈泡狀態與統計數據

---

## 🛠️ 系統架構 (System Architecture)

Camera
↓
電腦視覺辨識（九宮格 + 手掌偵測）
↓
AWS（MQTT Broker）
↓
ESP8266
↓
9 顆燈泡（對應九宮格）
↓
Web Dashboard（狀態顯示 + 熱區分析）


---

## 🔧 技術堆疊 (Tech Stack)

### 軟體
- **Computer Vision**: Python / OpenCV / mediapipe
- **Cloud**: AWS
- **Messaging Protocol**: MQTT
- **Web Dashboard**: HTML / FastAPI / Chart.js
- **Data Processing**: Python

### 硬體
- **攝影機**：電腦內建或 USB Camera
- **IoT 開發板**：ESP8266
- **輸出裝置**：9 顆燈泡（LED）

---

## 🔌 硬體配置 (Hardware Setup)

### ESP8266 燈泡對應說明（範例）

| 九宮格位置 | GPIO | 燈泡 |
|----------|------|------|
| 左上 | GPIO0 | LED 1 |
| 上中 | GPIO2 | LED 2 |
| 右上 | GPIO4 | LED 3 |
| 左中 | GPIO5 | LED 4 |
| 中央 | GPIO12 | LED 5 |
| 右中 | GPIO13 | LED 6 |
| 左下 | GPIO14 | LED 7 |
| 下中 | GPIO15 | LED 8 |
| 右下 | GPIO16 | LED 9 |

（實際 GPIO 可依電路設計調整）

---

## 💻 安裝與執行 (Installation)

### 1 影像辨識端（電腦）

```bash
pip install -r requirements.txt
python main.py
```

功能：
- 啟動攝影機
- 執行九宮格切割
- 進行手掌偵測
- 將結果傳送至 AWS MQTT

---

### 2 ESP8266 設定

使用 Arduino IDE 開啟 esp8266_mqtt.ino
修改以下設定：
- const char* ssid = "你的WiFi名稱";
- const char* password = "你的WiFi密碼";
上傳程式至 ESP8266

---

### 3 Web Dashboard

```bash
cd Web_Dashboard
uvicorn app:app --host 0.0.0.0 --port 8000
```


功能：
- 顯示 9 顆燈泡即時狀態
- 統計每格開燈次數
- 計算亮燈超過 10 秒的時間
- 視覺化人流熱區

