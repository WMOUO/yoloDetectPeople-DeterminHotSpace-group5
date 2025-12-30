#include <ESP8266WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>

// ==========================================
// 1. Wi-Fi 設定
// ==========================================
const char* WIFI_SSID = "wifi_name";
const char* WIFI_PASSWORD = "wifi_password";

// ==========================================
// 2. AWS 設定 (請填入 B 組員給的資料)
// ==========================================
const char* AWS_IOT_ENDPOINT = "a10eer929bk2gd-ats.iot.us-east-1.amazonaws.com";
const char* AWS_IOT_TOPIC = "project/esp8266_led";
const char* AWS_IOT_CLIENT_ID = "ESP8266_9Grid_Project";

// ==========================================
// 3. AWS 憑證 (請填入 B 組員給的資料)
// ==========================================
static const char AWS_CERT_CA[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
MIIDQTCCAimgAwIBAgITBmyfz5m/jAo54vB4ikPmljZbyjANBgkqhkiG9w0BAQsF
ADA5MQswCQYDVQQGEwJVUzEPMA0GA1UEChMGQW1hem9uMRkwFwYDVQQDExBBbWF6
b24gUm9vdCBDQSAxMB4XDTE1MDUyNjAwMDAwMFoXDTM4MDExNzAwMDAwMFowOTEL
MAkGA1UEBhMCVVMxDzANBgNVBAoTBkFtYXpvbjEZMBcGA1UEAxMQQW1hem9uIFJv
b3QgQ0EgMTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBALJ4gHHKeNXj
ca9HgFB0fW7Y14h29Jlo91ghYPl0hAEvrAIthtOgQ3pOsqTQNroBvo3bSMgHFzZM
9O6II8c+6zf1tRn4SWiw3te5djgdYZ6k/oI2peVKVuRF4fn9tBb6dNqcmzU5L/qw
IFAGbHrQgLKm+a/sRxmPUDgH3KKHOVj4utWp+UhnMJbulHheb4mjUcAwhmahRWa6
VOujw5H5SNz/0egwLX0tdHA114gk957EWW67c4cX8jJGKLhD+rcdqsq08p8kDi1L
93FcXmn/6pUCyziKrlA4b9v7LWIbxcceVOF34GfID5yHI9Y/QCB/IIDEgEw+OyQm
jgSubJrIqg0CAwEAAaNCMEAwDwYDVR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8EBAMC
AYYwHQYDVR0OBBYEFIQYzIU07LwMlJQuCFmcx7IQTgoIMA0GCSqGSIb3DQEBCwUA
A4IBAQCY8jdaQZChGsV2USggNiMOruYou6r4lK5IpDB/G/wkjUu0yKGX9rbxenDI
U5PMCCjjmCXPI6T53iHTfIUJrU6adTrCC2qJeHZERxhlbI1Bjjt/msv0tadQ1wUs
N+gDS63pYaACbvXy8MWy7Vu33PqUXHeeE6V/Uq2V8viTO96LXFvKWlJbYK8U90vv
o/ufQJVtMVT8QtPHRh8jrdkPSHCa2XV4cdFyQzR1bldZwgJcJmApzyMZFo6IQ6XU
5MsI+yMRQ+hDKXJioaldXgjUkK642M4UwtBV8ob2xJNDd2ZhwLnoQdeXeGADbkpy
rqXRfboQnoZsG4q5WTP468SQvvG5
-----END CERTIFICATE-----
)EOF";

static const char AWS_CERT_CRT[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
MIIDWTCCAkGgAwIBAgIUSM9yBYvoLMO5eds6wyotIaLw6T4wDQYJKoZIhvcNAQEL
BQAwTTFLMEkGA1UECwxCQW1hem9uIFdlYiBTZXJ2aWNlcyBPPUFtYXpvbi5jb20g
SW5jLiBMPVNlYXR0bGUgU1Q9V2FzaGluZ3RvbiBDPVVTMB4XDTI1MTIyODE1MTAw
OFoXDTQ5MTIzMTIzNTk1OVowHjEcMBoGA1UEAwwTQVdTIElvVCBDZXJ0aWZpY2F0
ZTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAMkXXTvH0kGbp7uomnLZ
KZ7C1A6999ytsD4D9d55UC/qRzWE9RDDPyXQ7m9Zu5whtqwdx0Q/D0XwFsxXbJ6o
zZUSQBa13Lmj53qQsKqXCb5qSoA8KLc2L0/Z9aXIyetEUqKkF0zpfJ3E8wj7QO4S
ea1r9wQVwoMkTWJXYtkEPZpWzn6Ju4aogxuGCKBsiYr1zFj9q6QNn/bNu8a8CsWl
hd1CvPIsNlYx29KfdxKvfIYX8/jGBL/Lwz44W/2LXTwyFDCsKFgH/SCS7XLOoBQZ
xvwyy45Q8bLCpjkhReA6aTnD+eCPmNtn1VTyTMWCwpq90/iL+f2ZebSSOrSywEA4
J28CAwEAAaNgMF4wHwYDVR0jBBgwFoAUGUD1boEFJcPzZWl2QK4gq3F5mRowHQYD
VR0OBBYEFOoj0dOhdXASeAsBwShHCehIYIzOMAwGA1UdEwEB/wQCMAAwDgYDVR0P
AQH/BAQDAgeAMA0GCSqGSIb3DQEBCwUAA4IBAQAAe7+6NqNTymAF9rRD9rP8WbOZ
PIPExTKUTWqAO1R3DY8tvjBB9qORYJ7YTeIVWxtqnQFVBapNoyBxxip+GzH0HZc8
dFL0Y2zTF2cH6zZr3CcChXaOdRK7O/OuTAAmfqpcYCZQ7rEi9jTviW4exBqp/Ad1
xgkQpVESabWddAebnRuBQOT+ZqaNH2ssgs48HUwFqhBJ6bL/+h3xYQBVJXQnPZJF
5VOy+s7IEFOtY59z5yLSSxJdmVg7SEaZ6lsitKdJWzAkJbK7roklfYJRWMDcsWSb
gobI8uOGfAMYDqiAJys51mbrtD7tOEQcqygR7R3r//V0Gc8Miy6nVvN/PAuz
-----END CERTIFICATE-----

)EOF";

static const char AWS_CERT_PRIVATE[] PROGMEM = R"EOF(
-----BEGIN RSA PRIVATE KEY-----
MIIEpQIBAAKCAQEAyRddO8fSQZunu6iactkpnsLUDr333K2wPgP13nlQL+pHNYT1
EMM/JdDub1m7nCG2rB3HRD8PRfAWzFdsnqjNlRJAFrXcuaPnepCwqpcJvmpKgDwo
tzYvT9n1pcjJ60RSoqQXTOl8ncTzCPtA7hJ5rWv3BBXCgyRNYldi2QQ9mlbOfom7
hqiDG4YIoGyJivXMWP2rpA2f9s27xrwKxaWF3UK88iw2VjHb0p93Eq98hhfz+MYE
v8vDPjhb/YtdPDIUMKwoWAf9IJLtcs6gFBnG/DLLjlDxssKmOSFF4DppOcP54I+Y
22fVVPJMxYLCmr3T+Iv5/Zl5tJI6tLLAQDgnbwIDAQABAoIBAGXbe9JICOxKl8+q
O3FpJnfQX/GHsAELyXXgM64Y7NEYbjFhw3BWNapGBkBIx4ryWMEd5E1hU68tSZ7/
uXk0L84OjH/0ZnVx3FJs78+46aqV1F7YGheTTqu3z4HGDuEonmLbkyHWMtUHacNm
4SC2IwQA6AIds4UR4lCpytv6FeoSn+c98fkcNyJuglwX1e52aeG4hxEWdudr/KVi
Oo7hBSO2ZyG8eTtSl0cE3REY9x1Z4uEs5CXy964K2jDJMQCSDF68/Yc2n3RM5ast
1ZyQvaWCPZRy2/L7/lxx4KcRvJGYJWSNWZPh7Wp7biUEh2Al+YLO/68T4qm9Umhv
zgcHTKECgYEA8xbDvPjTn+oB1VUO47qGEdLo21FUEBOmmbA0JeIEuPaw9RsgDkhK
5cX76rQWyXjoKtBx4sCDLAi4En3HAxztrqVnF3nHzfcIzUYIR9FQb4XNfoK1/rCv
sZrjC+YzBlCCeDU38CN8FEC369KfL1OlN11jDDiMYhIzE3vtFzATAc0CgYEA08WQ
rmPFJ1BxgDzhsEDu4K45wzNfVZpFDedIIjRjmYD2cY9E9DOw9WuF/wNVylqi0BMT
pvUErwPhJSn8axMPHdGHano2Ype4/4Ha2hvO+Dhc8sv+xHIUjJkuq8uOAYBO/pg6
F1OcKKEpcFaJCTtVPowaQdfHVWiQegB1iBDQQisCgYEAyAwq5x/qoEZmXdaS20wL
uy1TXfGO+XACgaXlNGvNMR4qwHsjJT3PDUqiJyMvQXwTq/BAWLfO+vTt7qG9nk03
OKt7rHEWweQTRULl25xg0nZNh1gwR7nFzKZHROqbgQ3OYPiC4UeCe/RKp3J8d+kh
JO/gbBU5ShfqGpW4poV0jt0CgYEAidUZsNdQ96Cc7wkxH0Vz9JqRD+J81ztcXIs+
4LxWYw+T1x+XkpWeRG3iPbNPADBzrZfs/4qTrNGKlWS5XHuAKDk6uOuoQA1eJDbB
WZol4FrW7FQnknZpt4Tv4nLPD10SjRRJIuuRRMR4Mxyvfmm2tsn7QQWPQKCZAD8S
QCgpVBcCgYEArCA2rh1Guf6vmMooaO1B1IAji26fD/Ii8xaYeZV1DfIQp+Z7hVVe
MLZc8JSTpVxfmeaRYtHj6GSU8PE9aM8TZkPZbMkXHwW/36BjCqG3AiDCBgN0cHql
3/TlSjF/JqkHjZU6oZtOs5jRz0p0zrujrN/WSq+yt7xPCHUnfM4fuDA=
-----END RSA PRIVATE KEY-----
)EOF";

// ==========================================
// 4. 九宮格腳位設定 (關鍵修改)
// ==========================================
// 我們使用 D0 ~ D8 共 9 支腳位
// 對應順序：第1格(D0), 第2格(D1)... 到 第9格(D8)
const int LED_COUNT = 9;
const int LED_PINS[LED_COUNT] = {D0, D1, D2, D3, D4, D5, D6, D7, D8};

WiFiClientSecure net;
PubSubClient client(net);

void connectAWS() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.println("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWi-Fi Connected!");

  // ========================================================
  // 請新增這段：NTP 對時 (修復 rc=-2 的關鍵)
  // ========================================================
  Serial.print("Setting time using SNTP");
  configTime(0, 0, "pool.ntp.org", "time.nist.gov"); // 向網路校時伺服器抓時間
  time_t now = time(nullptr);
  while (now < 1000) { // 如果時間小於 1000 (代表還是 1970年)，就繼續等
    delay(500);
    Serial.print(".");
    now = time(nullptr);
  }
  Serial.println("\nTime synced!");
  struct tm timeinfo;
  gmtime_r(&now, &timeinfo);
  Serial.print("Current time: ");
  Serial.print(asctime(&timeinfo));
  // ========================================================
  // 新增結束
  // ========================================================

  net.setTrustAnchors(new X509List(AWS_CERT_CA));
  net.setClientRSACert(new X509List(AWS_CERT_CRT), new PrivateKey(AWS_CERT_PRIVATE));

  client.setServer(AWS_IOT_ENDPOINT, 8883);
  client.setCallback(messageHandler);

  Serial.println("Connecting to AWS IoT");
  while (!client.connected()) {
    Serial.print(".");
    if (client.connect(AWS_IOT_CLIENT_ID)) {
      Serial.println("\nAWS IoT Connected!");
      client.subscribe(AWS_IOT_TOPIC);
      Serial.println("Subscribed to topic!");
    } else {
      Serial.print("Failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}

// 輔助函式：切換燈光
// 輸入 1-9 代表亮哪一顆，輸入 0 代表全關
void switchLED(int targetZone) {
  for (int i = 0; i < LED_COUNT; i++) {
    // 陣列索引是 0~8，所以 targetZone 要減 1
    // 如果目前的索引 i 等於 (目標區域 - 1)，就開燈，否則關燈
    if (i == (targetZone - 1)) {
      digitalWrite(LED_PINS[i], HIGH);
    } else {
      digitalWrite(LED_PINS[i], LOW);
    }
  }
}

// 訊息處理函式
// 收到訊息時的處理邏輯 (針對 11/10 協議修正版)
void messageHandler(char* topic, byte* payload, unsigned int length) {
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  
  Serial.print("Received: ");
  Serial.println(message); // 這裡會印出收到的原始訊息，例如 "11" 或 "20"

  int val = message.toInt();   // 把字串 "11" 轉成數字 11
  int targetZone = val / 10;   // 十位數：11 / 10 = 1 (第1格)
  int state = val % 10;        // 個位數：11 % 10 = 1 (亮)

  // 檢查是否在 1~9 的範圍內
  if (targetZone >= 1 && targetZone <= 9) {
    // 陣列索引是 0 開始，所以要減 1 (第1格是對應 LED_PINS[0])
    int pinIndex = targetZone - 1;

    if (state == 1) {
      digitalWrite(LED_PINS[pinIndex], HIGH); // 亮燈
      Serial.print("Action: Zone ");
      Serial.print(targetZone);
      Serial.println(" -> ON");
    } 
    else if (state == 0) {
      digitalWrite(LED_PINS[pinIndex], LOW);  // 關燈
      Serial.print("Action: Zone ");
      Serial.print(targetZone);
      Serial.println(" -> OFF");
    }
  } 
  else {
    // 收到奇怪的數字 (例如 99 或 0)
    Serial.println("Ignore: Invalid zone command");
  }
}

void setup() {
  Serial.begin(115200);

  // 初始化所有腳位為 OUTPUT，並先關閉
  for (int i = 0; i < LED_COUNT; i++) {
    pinMode(LED_PINS[i], OUTPUT);
    digitalWrite(LED_PINS[i], LOW);
  }

  connectAWS();
}

void loop() {
  if (!client.connected()) {
    connectAWS();
  }
  client.loop();
}
