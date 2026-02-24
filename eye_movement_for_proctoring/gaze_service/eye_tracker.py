"""
Eye Tracking Service using MediaPipe FaceMesh
Writes gaze CSV incrementally so it ALWAYS exists
Safe with force-kill / subprocess terminate
"""

import cv2
import mediapipe as mp
import numpy as np
import time
import csv
import os
import argparse
import sys


class ProctoringSystem:
    def __init__(self, camera_id, session_id):
        self.session_id = session_id

        # =========================
        # MediaPipe
        # =========================
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        self.cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        self.LEFT_IRIS = [474, 475, 476, 477]
        self.RIGHT_IRIS = [469, 470, 471, 472]
        self.LEFT_EYE = [33, 133, 160, 159, 158, 157, 173, 144]
        self.RIGHT_EYE = [362, 263, 387, 386, 385, 384, 398, 373]

        self.LOOK_AWAY_THRESHOLD = 0.15
        self.frame_index = 0

        # =========================
        # PATHS (MATCH ANALYZER)
        # =========================
        BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.log_dir = os.path.join(BASE_DIR, "proctoring_logs", "gaze")
        os.makedirs(self.log_dir, exist_ok=True)

        self.csv_path = os.path.join(
            self.log_dir,
            f"gaze_{self.session_id}.csv"
        )

        #STOP condition added on 10/2 14:21
        self.stop_file = os.path.join(
            self.log_dir,
            f"STOP_{self.session_id}.flag"
        )


        # OVERWRITE every run
        self.csv_file = open(self.csv_path, "w", newline="")
        self.writer = csv.DictWriter(
            self.csv_file,
            fieldnames=[
                "frame_index",
                "timestamp",
                "face_detected",
                "looking_at_screen",
                "direction",
                "horizontal_ratio",
                "vertical_ratio"
            ]
        )
        self.writer.writeheader()
        self.csv_file.flush()

        print(f"[GAZE] Writing CSV → {self.csv_path}")

    # =========================
    # Gaze helpers
    # =========================
    def get_eye_position(self, landmarks, eye_indices, iris_indices, w, h):
        eye_points = [(landmarks[i].x * w, landmarks[i].y * h) for i in eye_indices]
        iris_points = [(landmarks[i].x * w, landmarks[i].y * h) for i in iris_indices]

        iris_x = np.mean([p[0] for p in iris_points])
        iris_y = np.mean([p[1] for p in iris_points])

        eye_left = min(p[0] for p in eye_points)
        eye_right = max(p[0] for p in eye_points)
        eye_top = min(p[1] for p in eye_points)
        eye_bottom = max(p[1] for p in eye_points)

        eye_width = eye_right - eye_left
        eye_height = eye_bottom - eye_top

        h_ratio = (iris_x - (eye_left + eye_width / 2)) / (eye_width / 2) if eye_width else 0
        v_ratio = (iris_y - (eye_top + eye_height / 2)) / (eye_height / 2) if eye_height else 0

        return h_ratio, v_ratio

    def detect_gaze(self, landmarks, w, h):
        lh, lv = self.get_eye_position(landmarks.landmark, self.LEFT_EYE, self.LEFT_IRIS, w, h)
        rh, rv = self.get_eye_position(landmarks.landmark, self.RIGHT_EYE, self.RIGHT_IRIS, w, h)

        avg_h = (lh + rh) / 2
        avg_v = (lv + rv) / 2

        looking = abs(avg_h) < self.LOOK_AWAY_THRESHOLD and abs(avg_v) < self.LOOK_AWAY_THRESHOLD + 0.1

        direction = "CENTER"
        if not looking:
            if avg_h < -self.LOOK_AWAY_THRESHOLD:
                direction = "LEFT"
            elif avg_h > self.LOOK_AWAY_THRESHOLD:
                direction = "RIGHT"
            elif avg_v > self.LOOK_AWAY_THRESHOLD:
                direction = "DOWN"
            elif avg_v < -self.LOOK_AWAY_THRESHOLD:
                direction = "UP"

        return looking, direction, avg_h, avg_v

    # =========================
    # MAIN LOOP
    # =========================
    def run(self):
        if not self.cap.isOpened():
            print("[GAZE] Camera failed to open")
            return

        while True:

            # CHECK FOR STOP SIGNAL added on 10/2 14:23
            if os.path.exists(self.stop_file):
                print("[GAZE] Stop signal detected, shutting down camera")
                break


            ret, frame = self.cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(rgb)

            face_detected = False
            looking = False
            direction = "NO_FACE"
            h_ratio = 0
            v_ratio = 0

            if results.multi_face_landmarks:
                face_detected = True
                lm = results.multi_face_landmarks[0]
                looking, direction, h_ratio, v_ratio = self.detect_gaze(lm, w, h)

            self.writer.writerow({
                "frame_index": self.frame_index,
                "timestamp": time.strftime("%H:%M:%S"),
                "face_detected": face_detected,
                "looking_at_screen": looking,
                "direction": direction,
                "horizontal_ratio": h_ratio,
                "vertical_ratio": v_ratio
            })
            self.csv_file.flush()

            self.frame_index += 1
            cv2.waitKey(1)

        self.cleanup()

    def cleanup(self):
        self.cap.release()
        self.csv_file.close()
        cv2.destroyAllWindows()
        print("[GAZE] Tracker exited cleanly")


# =========================
# ENTRY
# =========================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--session_id", required=True)
    args = parser.parse_args()

    ProctoringSystem(
        camera_id=1,
        session_id=args.session_id
    ).run()
