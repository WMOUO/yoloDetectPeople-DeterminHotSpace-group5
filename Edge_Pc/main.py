import cv2
import time
import json
import mediapipe as mp

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from awscrt import io, mqtt
from awsiot import mqtt_connection_builder

PRINT_INTERVAL_SEC = 0.5

SEND_TO_AWS = True
IOT_ENDPOINT = "a10eer929bk2gd-ats.iot.us-east-1.amazonaws.com"
CLIENT_ID = "cam-001"
TOPIC = "project/esp8266_led"

CERT_PATH = "./device.pem.crt"
KEY_PATH = "./private.pem.key"
CA_PATH = "./AmazonRootCA1.pem"

def point_to_grid_id(cx: int, cy: int, w: int, h: int) -> int:
    cell_w = w / 3.0
    cell_h = h / 3.0
    col = int(cx / cell_w)
    row = int(cy / cell_h)
    col = max(0, min(2, col))
    row = max(0, min(2, row))
    return row * 3 + col + 1

def draw_grid(frame):
    h, w = frame.shape[:2]
    x1, x2 = int(w / 3), int(2 * w / 3)
    y1, y2 = int(h / 3), int(2 * h / 3)
    cv2.line(frame, (x1, 0), (x1, h), (255, 255, 255), 3)
    cv2.line(frame, (x2, 0), (x2, h), (255, 255, 255), 3)
    cv2.line(frame, (0, y1), (w, y1), (255, 255, 255), 3)
    cv2.line(frame, (0, y2), (w, y2), (255, 255, 255), 3)

def grid_id_to_code(grid_id: int, is_on: bool) -> int:
    return grid_id * 10 + (1 if is_on else 0)

def format_grid_codes(codes_1_to_9):
    return (
        f"{codes_1_to_9[0]} | {codes_1_to_9[1]} | {codes_1_to_9[2]}\n"
        f"{codes_1_to_9[3]} | {codes_1_to_9[4]} | {codes_1_to_9[5]}\n"
        f"{codes_1_to_9[6]} | {codes_1_to_9[7]} | {codes_1_to_9[8]}"
    )

def build_mqtt_connection():
    event_loop_group = io.EventLoopGroup(1)
    host_resolver = io.DefaultHostResolver(event_loop_group)
    client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)
    return mqtt_connection_builder.mtls_from_path(
        endpoint=IOT_ENDPOINT,
        cert_filepath=CERT_PATH,
        pri_key_filepath=KEY_PATH,
        ca_filepath=CA_PATH,
        client_bootstrap=client_bootstrap,
        client_id=CLIENT_ID,
        clean_session=False,
        keep_alive_secs=30
    )

def mqtt_connect(mqtt_connection):
    print("[MQTT] Connecting...")
    mqtt_connection.connect().result()
    print("[MQTT] Connected.")

def mqtt_publish_code(mqtt_connection, code: int):
    payload = code
    mqtt_connection.publish(
        topic=TOPIC,
        payload=json.dumps(payload, ensure_ascii=False),
        qos=mqtt.QoS.AT_LEAST_ONCE
    )

def mqtt_disconnect(mqtt_connection):
    try:
        mqtt_connection.disconnect().result()
        print("[MQTT] Disconnected.")
    except Exception as e:
        print("[MQTT] Disconnect error:", repr(e))

def main():
    # ===== MediaPipe Tasks: HandLandmarker =====
    # 需要先把 hand_landmarker.task 下載到專案目錄
    model_path = "./hand_landmarker.task"

    base_options = python.BaseOptions(model_asset_path=model_path)
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2
    )

    landmarker = vision.HandLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("無法開啟攝影機")

    mqtt_connection = None
    if SEND_TO_AWS:
        mqtt_connection = build_mqtt_connection()
        mqtt_connect(mqtt_connection)

    last_print_t = 0.0
    last_on_codes = set()
    last_status_text = "[Grid]\n(尚未輸出)"

    ts_ms = 0  # VIDEO mode 需要遞增 timestamp（毫秒）

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            draw_grid(frame)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            ts_ms += 33  # 粗略用 30fps; 也可改成用 time.time() 算
            result = landmarker.detect_for_video(mp_image, ts_ms)

            grid_state = {i: 0 for i in range(1, 10)}

            # result.hand_landmarks 是 list[hand]，每個 hand 是 21 個 landmark（normalized x,y）
            if result.hand_landmarks:
                for hand_lms in result.hand_landmarks:
                    # 掌心近似點：0(手腕)+5+17 平均
                    idxs = [0, 5, 17]
                    xs = [hand_lms[i].x for i in idxs]
                    ys = [hand_lms[i].y for i in idxs]
                    cx = int(sum(xs) / len(xs) * w)
                    cy = int(sum(ys) / len(ys) * h)

                    grid_id = point_to_grid_id(cx, cy, w, h)
                    grid_state[grid_id] = 1

                    cv2.circle(frame, (cx, cy), 8, (0, 255, 0), -1)
                    code = grid_id_to_code(grid_id, True)
                    cv2.putText(frame, f"palm cell={grid_id} code={code}",
                                (cx + 10, cy - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            now = time.time()
            if now - last_print_t >= PRINT_INTERVAL_SEC:
                last_print_t = now

                codes = [grid_id_to_code(i, grid_state[i] == 1) for i in range(1, 10)]
                grid_text = format_grid_codes(codes)
                last_status_text = "[Grid]\n" + grid_text
                print(last_status_text)

                on_codes = {grid_id_to_code(i, True) for i in range(1, 10) if grid_state[i] == 1}
                print("[ON_CODES]", sorted(on_codes) if on_codes else "none")

                if SEND_TO_AWS and mqtt_connection is not None:
                    new_codes = on_codes - last_on_codes
                    gone_codes = last_on_codes - on_codes

                    for code in sorted(new_codes):
                        mqtt_publish_code(mqtt_connection, code)
                        print("[MQTT] Published:", code)

                    # 若你不想送 off，把這段註解掉
                    for code in sorted(gone_codes):
                        off_code = (code // 10) * 10
                        mqtt_publish_code(mqtt_connection, off_code)
                        print("[MQTT] Published:", off_code)

                    last_on_codes = on_codes

            y0 = 30
            for i, line in enumerate(last_status_text.splitlines()):
                cv2.putText(frame, line, (10, y0 + i * 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

            cv2.imshow("HandLandmarker (Tasks) + 3x3 Grid Codes", frame)
            if (cv2.waitKey(1) & 0xFF) == 27:
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        landmarker.close()
        if SEND_TO_AWS and mqtt_connection is not None:
            mqtt_disconnect(mqtt_connection)

if __name__ == "__main__":
    main()
