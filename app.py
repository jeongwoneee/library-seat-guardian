import streamlit as st
import cv2
import time
from ultralytics import YOLO
import tempfile
import os

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="Library Seat Guardian",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. 시스템 구동 상태 및 타이머 메모리 세션 초기화
if 'deployed' not in st.session_state:
    st.session_state.deployed = False

if 'seat_timers' not in st.session_state:
    st.session_state.seat_timers = {
        '1번 좌석 (왼쪽)': {'status': 'Available', 'start_time': None, 'elapsed': 0},
        '2번 좌석 (오른쪽)': {'status': 'Available', 'start_time': None, 'elapsed': 0}
    }

# 3. 커스텀 CSS 주입
st.markdown("""
<style>
    .main { background-color: #F8FAFC; }
    .header-container {
        display: flex; align-items: center; gap: 12px;
        padding-bottom: 1rem; border-bottom: 2px solid #E2E8F0; margin-bottom: 2rem;
    }
    .header-title { font-size: 2.2rem; font-weight: 800; color: #1E293B; }
    .header-subtitle { font-size: 1.1rem; color: #64748B; font-weight: 400; margin-top: auto; margin-bottom: 6px; }
    .seat-card {
        background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 14px;
        padding: 1.5rem; margin-bottom: 1.2rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .seat-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
    .seat-title { font-size: 1.25rem; font-weight: 700; color: #334155; }
    .badge { padding: 6px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 700; }
    .badge-active { background-color: #DCFCE7; color: #16A34A; }
    .badge-away { background-color: #FFEDD5; color: #EA580C; }
    .badge-sleeping { background-color: #F3E8FF; color: #9333EA; }
    .badge-available { background-color: #F1F5F9; color: #64748B; }
    .timer-label { font-size: 0.85rem; color: #64748B; font-weight: 500; }
    .timer-value { font-size: 2.2rem; font-weight: 800; color: #0F172A; margin-top: -2px; }
    .timer-unit { font-size: 1.2rem; font-weight: 500; color: #64748B; }
    
    .custom-alert {
        margin-top: 1rem; padding: 1rem; border-radius: 8px;
        background-color: #FEF2F2; border-left: 4px solid #EF4444;
    }
    .custom-alert.warning {
        background-color: #FFFBEB; border-left: 4px solid #F59E0B;
    }
    .alert-title { font-weight: 700; font-size: 0.95rem; color: #1E293B; margin-bottom: 0.25rem; }
    .alert-desc { font-size: 0.88rem; color: #475569; line-height: 1.4; }
</style>
""", unsafe_allow_html=True)

# 4. YOLOv4 모델 로드
@st.cache_resource
def load_model():
    return YOLO('best.pt')

model = load_model()

# 5. 사이드바 구성
with st.sidebar:
    st.markdown("### 📁 비디오 설정")
    st.caption("영상을 업로드하세요")
    uploaded_file = st.file_uploader("Upload Demo Video", type=["mp4", "avi", "mov"], label_visibility="collapsed")
    
    st.text("")
    st.markdown("---")
    st.markdown("### ⚙️ 시스템 제어")
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("Deploy", type="primary", use_container_width=True):
            st.session_state.deployed = True
            st.rerun()
    with col_btn2:
        if st.button("Reset", type="secondary", use_container_width=True):
            st.session_state.deployed = False
            for seat in st.session_state.seat_timers:
                st.session_state.seat_timers[seat] = {'status': 'Available', 'start_time': None, 'elapsed': 0}
            st.rerun()

    st.text("")
    st.markdown("---")
    st.markdown("### 🪑 공간 관리")
    st.caption("관제 구역의 총 좌석 수를 설정하세요")
    total_seats = st.number_input("총 좌석 수 설정", min_value=2, value=4, step=1)

# 6. 메인 화면 헤더
st.markdown("""
<div class="header-container">
    <div class="header-title">🛡️ Library Seat Guardian</div>
    <div class="header-subtitle">실시간 좌석 관제 시스템</div>
</div>
""", unsafe_allow_html=True)

# 7. 메인 레이아웃 분할
col_cctv, col_dash = st.columns([1.3, 1])

with col_cctv:
    st.markdown("#### 📹 CCTV 실시간 모니터링 피드")
    with st.container(border=True):
        frame_placeholder = st.empty()
    
    seats_status_placeholder = st.empty()

with col_dash:
    st.markdown("#### 📊 좌석별 관제 대시보드")
    dash_placeholder = st.empty()

# 하단 현황판 컴포넌트 렌더러 헬퍼 함수
def get_seats_status_html(total, occupied):
    available = max(0, total - occupied)
    avail_color = '#16A34A' if available > 0 else '#EF4444'
    return f"""
    <div style="display: flex; gap: 16px; margin-top: 1rem;">
        <div style="flex: 1; background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.2rem; text-align: center; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
            <div style="font-size: 0.88rem; color: #64748B; font-weight: 600;">🏢 전체 좌석 수</div>
            <div style="font-size: 2rem; font-weight: 800; color: #1E293B; margin-top: 4px;">{total}<span style="font-size: 1.1rem; font-weight: 500; color: #64748B;"> 석</span></div>
        </div>
        <div style="flex: 1; background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.2rem; text-align: center; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
            <div style="font-size: 0.88rem; color: #64748B; font-weight: 600;">🍀 이용 가능 좌석 수</div>
            <div style="font-size: 2rem; font-weight: 800; color: {avail_color}; margin-top: 4px;">{available}<span style="font-size: 1.1rem; font-weight: 500; color: #64748B;"> 석</span></div>
        </div>
    </div>
    """

# 8. 시스템 작동 로직
if uploaded_file is not None and st.session_state.deployed:
    uploaded_file.seek(0)
    
    tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    tfile.write(uploaded_file.read())
    tfile.close()

    cap = cv2.VideoCapture(tfile.name)

    # ⚡ 초고속 렌더링용 연산 메모리 초기화
    frame_count = 0
    SKIP_FRAMES = 3  # ◀ 3프레임당 1번만 YOLO 수행 (부하 66% 감소)
    last_boxes = []  # ◀ 박스 위치 캐싱 저장소 (깜빡임 원천 차단)

    while cap.isOpened() and st.session_state.deployed:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        # ⚡ [최적화 1] 입력 해상도 강제 축소 -> 스트림릿 전송 부하 5배 감소
        frame = cv2.resize(frame, (640, 360))
        height, width, _ = frame.shape
        mid_x = width / 2

        # ⚡ [최적화 2] 프레임 스킵 분기 처리
        if frame_count % SKIP_FRAMES == 1:
            # ⚡ [최적화 3] YOLO 입력 해상도를 imgsz=320으로 낮춰 CPU 추론 속도 극대화
            results = model(frame, imgsz=384, verbose=False)
            
            last_boxes = []
            current_frame_status = {'1번 좌석 (왼쪽)': 'Available', '2번 좌석 (오른쪽)': 'Available'}

            for box in results[0].boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                center_x = (x1 + x2) / 2
                label = results[0].names[int(box.cls[0])]
                conf = float(box.conf[0])

                # 최적화용 박스 좌표 캐싱
                last_boxes.append((x1, y1, x2, y2, label, conf))

                if center_x < mid_x:
                    seat_key = '1번 좌석 (왼쪽)'
                else:
                    seat_key = '2번 좌석 (오른쪽)'

                if label in ['Away', 'Sleeping', 'Active']:
                    current_frame_status[seat_key] = label

            # 시간 연산 및 상태 업데이트
            current_time = time.time()
            for seat, status in current_frame_status.items():
                if status in ['Away', 'Sleeping', 'Active']:
                    if st.session_state.seat_timers[seat]['status'] != status:
                        st.session_state.seat_timers[seat]['status'] = status
                        st.session_state.seat_timers[seat]['start_time'] = current_time
                        st.session_state.seat_timers[seat]['elapsed'] = 0
                    else:
                        st.session_state.seat_timers[seat]['elapsed'] = int(current_time - st.session_state.seat_timers[seat]['start_time'])
                else:
                    st.session_state.seat_timers[seat]['status'] = status
                    st.session_state.seat_timers[seat]['start_time'] = None
                    st.session_state.seat_timers[seat]['elapsed'] = 0

        # ⚡ [최적화 핵심] YOLO를 돌리지 않는 프레임에도 캐싱된 박스를 OpenCV로 초고속 직접 렌더링
        for x1, y1, x2, y2, label, conf in last_boxes:
            if label == 'Active': color = (74, 163, 22)      # 초록 (BGR)
            elif label == 'Sleeping': color = (234, 51, 147)  # 보라 (BGR)
            else: color = (0, 0, 255)                         # 빨강 (BGR)
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"{label} {conf:.2f}", (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # 비디오 출력 (기존 time.sleep 제거하여 최고 속도 보장)
        annotated_frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_placeholder.image(annotated_frame_rgb, channels="RGB", use_container_width=True)

        # 피드 아래 현황판 실시간 연동
        occupied_count = sum(1 for info in st.session_state.seat_timers.values() if info['status'] in ['Away', 'Sleeping', 'Active'])
        seats_status_placeholder.markdown(get_seats_status_html(total_seats, occupied_count), unsafe_allow_html=True)

        # 대시보드 카드 렌더링
        with dash_placeholder.container():
            for seat, info in st.session_state.seat_timers.items():
                if info['status'] == 'Away':
                    badge_class, badge_text, label_text = "badge-away", "자리비움 (Away)", "누적 부재 시간"
                elif info['status'] == 'Sleeping':
                    badge_class, badge_text, label_text = "badge-sleeping", "취침 중 (Sleeping)", "누적 취침 시간"
                elif info['status'] == 'Active':
                    badge_class, badge_text, label_text = "badge-active", "정상 사용 중 (Active)", "총 이용 시간"
                else:
                    badge_class, badge_text, label_text = "badge-available", "이용 가능 (Available)", "공석 대기 시간"

                alert_html = ""
                if info['status'] == 'Away' and info['elapsed'] >= 10:
                    alert_html = f'<div class="custom-alert"><div class="alert-title">🚨 장시간 미점유 경고!</div><div class="alert-desc">{seat} 이용자가 10초 이상 자리를 비웠습니다. 무단 점유 해제 조치 대상입니다.</div></div>'
                elif info['status'] == 'Sleeping' and info['elapsed'] >= 15:
                    alert_html = f'<div class="custom-alert warning"><div class="alert-title">🔔 진동 알림 전송!</div><div class="alert-desc">{seat} 이용자가 15초 이상 취침 중입니다. 깨우기 진동 알림을 발송합니다.</div></div>'

                card_html = f'<div class="seat-card"><div class="seat-header"><div class="seat-title">🪑 {seat}</div><div class="badge {badge_class}">{badge_text}</div></div><div><div class="timer-label">{label_text}</div><div class="timer-value">{info["elapsed"]} <span class="timer-unit">초</span></div></div>{alert_html}</div>'
                st.markdown(card_html, unsafe_allow_html=True)

    cap.release()
    try:
        os.unlink(tfile.name)
    except:
        pass

elif uploaded_file is not None and not st.session_state.deployed:
    st.success("🎯 영상 파일 업로드 완료! 왼쪽 사이드바의 [Deploy] 버튼을 누르면 실시간 AI 관제가 시작됩니다.")
else:
    st.info("💡 왼쪽 사이드바에서 비디오 파일(.mp4)을 업로드한 뒤 [Deploy] 버튼을 눌러주세요.")