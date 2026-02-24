import cv2
import numpy as np

# =========================
# CONFIG
# =========================
CAMERA_INDEX = 0
EYE_SIZE = (80, 40)

MIN_FEATURES = 6
BLINK_MIN = 2
BLINK_MAX = 6

# =========================
# CASCADES
# =========================
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)
eye_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_eye.xml"
)

# =========================
# OPTICAL FLOW PARAMS
# =========================
lk_params = dict(
    winSize=(15, 15),
    maxLevel=2,
    criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
)

# =========================
# HELPERS
# =========================
def normalize_eye(img):
    return cv2.resize(img, EYE_SIZE)

def iris_contrast_score(eye_gray):
    h, w = eye_gray.shape
    if h < 10 or w < 10:
        return 0.0

    center = eye_gray[int(0.3*h):int(0.7*h), int(0.3*w):int(0.7*w)]

    top    = eye_gray[:int(0.2*h), :]
    bottom = eye_gray[int(0.8*h):, :]
    left   = eye_gray[:, :int(0.2*w)]
    right  = eye_gray[:, int(0.8*w):]

    surround_mean = np.mean([
        np.mean(top),
        np.mean(bottom),
        np.mean(left),
        np.mean(right)
    ])

    return surround_mean - np.mean(center)

def select_eye_pair(eyes, face_w):
    pairs = []
    for i in range(len(eyes)):
        for j in range(i + 1, len(eyes)):
            (x1,y1,w1,h1) = eyes[i]
            (x2,y2,w2,h2) = eyes[j]

            if abs(w1 - w2) > 0.4 * max(w1, w2):
                continue
            if abs(y1 - y2) > 0.3 * max(h1, h2):
                continue
            if abs((x1 + w1/2) - (x2 + w2/2)) < face_w * 0.2:
                continue

            pairs.append((eyes[i], eyes[j]))

    if not pairs:
        return None

    return max(
        pairs,
        key=lambda p: abs((p[0][0]+p[0][2]/2)-(p[1][0]+p[1][2]/2))
    )

def init_features(eye):
    gray = cv2.cvtColor(eye, cv2.COLOR_BGR2GRAY)
    return cv2.goodFeaturesToTrack(
        gray,
        maxCorners=20,
        qualityLevel=0.01,
        minDistance=5
    )

def track(prev_gray, gray, pts):
    new_pts, status, _ = cv2.calcOpticalFlowPyrLK(
        prev_gray, gray, pts, None, **lk_params
    )
    if new_pts is None:
        return None
    return new_pts[status == 1]

def pupil_center(points):
    if points is None or len(points) == 0:
        return None
    c = np.mean(points, axis=0)
    return int(c[0]), int(c[1])

# =========================
# MAIN
# =========================
cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

locked = False
eye_boxes = None

pts_L = pts_R = None
prev_L = prev_R = None

blink_count = 0
blink_active = False

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    if len(faces) > 0:
        x, y, w, h = max(faces, key=lambda f: f[3])
        face = frame[y:y+h, x:x+w]
        face_gray = gray[y:y+h, x:x+w]

        # =========================
        # EYE DETECTION (ONCE)
        # =========================
        if not locked:
            candidates = eye_cascade.detectMultiScale(
                face_gray,
                scaleFactor=1.1,
                minNeighbors=3
            )
            candidates = [e for e in candidates if e[1] + e[3] < h * 0.6]

            pair = select_eye_pair(candidates, w)
            if pair:
                (ex1,ey1,ew1,eh1),(ex2,ey2,ew2,eh2) = pair
                eye1 = face[ey1:ey1+eh1, ex1:ex1+ew1]
                eye2 = face[ey2:ey2+eh2, ex2:ex2+ew2]

                if iris_contrast_score(cv2.cvtColor(eye1, cv2.COLOR_BGR2GRAY)) > 5 and \
                   iris_contrast_score(cv2.cvtColor(eye2, cv2.COLOR_BGR2GRAY)) > 5:
                    if ex1 < ex2:
                        eye_boxes = ((ex1,ey1,ew1,eh1),(ex2,ey2,ew2,eh2))
                    else:
                        eye_boxes = ((ex2,ey2,ew2,eh2),(ex1,ey1,ew1,eh1))
                    locked = True

        # =========================
        # TRACKING
        # =========================
        if locked:
            (lx,ly,lw,lh),(rx,ry,rw,rh) = eye_boxes

            left_eye  = normalize_eye(face[ly:ly+lh, lx:lx+lw])
            right_eye = normalize_eye(face[ry:ry+rh, rx:rx+rw])

            gray_L = cv2.cvtColor(left_eye, cv2.COLOR_BGR2GRAY)
            gray_R = cv2.cvtColor(right_eye, cv2.COLOR_BGR2GRAY)

            # LEFT
            if pts_L is None or prev_L is None or len(pts_L) < MIN_FEATURES:
                pts_L = init_features(left_eye)
                prev_L = gray_L
            else:
                new_L = track(prev_L, gray_L, pts_L)
                if new_L is not None and len(new_L) >= MIN_FEATURES:
                    pc = pupil_center(new_L)
                    if pc:
                        px = x + lx + int(pc[0] * lw / EYE_SIZE[0])
                        py = y + ly + int(pc[1] * lh / EYE_SIZE[1])
                        cv2.circle(frame, (px, py), 6, (0,0,255), 2)
                    pts_L = new_L.reshape(-1,1,2)
                    prev_L = gray_L
                else:
                    pts_L = None

            # RIGHT
            if pts_R is None or prev_R is None or len(pts_R) < MIN_FEATURES:
                pts_R = init_features(right_eye)
                prev_R = gray_R
            else:
                new_R = track(prev_R, gray_R, pts_R)
                if new_R is not None and len(new_R) >= MIN_FEATURES:
                    pc = pupil_center(new_R)
                    if pc:
                        px = x + rx + int(pc[0] * rw / EYE_SIZE[0])
                        py = y + ry + int(pc[1] * rh / EYE_SIZE[1])
                        cv2.circle(frame, (px, py), 6, (0,0,255), 2)
                    pts_R = new_R.reshape(-1,1,2)
                    prev_R = gray_R
                else:
                    pts_R = None

            # Blink logic
            visible = (0 if pts_L is None else len(pts_L)) + (0 if pts_R is None else len(pts_R))
            if visible < MIN_FEATURES:
                blink_count += 1
                blink_active = True
            else:
                if blink_active:
                    if blink_count > BLINK_MAX:
                        print("⚠ Prolonged eye closure")
                    blink_count = 0
                    blink_active = False

            # Debug eye boxes
            cv2.rectangle(frame,(x+lx,y+ly),(x+lx+lw,y+ly+lh),(0,255,0),1)
            cv2.rectangle(frame,(x+rx,y+ry),(x+rx+rw,y+ry+rh),(0,255,0),1)

        cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)

    cv2.imshow("Eye Tracking (Single Window)", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()