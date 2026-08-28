import os
import random
import io
from PIL import Image
import streamlit as st

# -----------------------------------------------------------------------------
# KONFIGURASI HALAMAN STREAMLIT
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="LPC Character Generator (Local)",
    page_icon="🎨",
    layout="wide"
)

# -----------------------------------------------------------------------------
# KONFIGURASI HIRARKI & SPESIFIKASI LPC
# -----------------------------------------------------------------------------
LPC_LAYER_ORDER = [
    'shadow', 'body', 'head', 'eyes', 'beards', 'hair', 
    'torso', 'legs', 'feet', 'arms', 'wrists', 'shoulders', 
    'neck', 'cape', 'backpack', 'quiver', 'hat', 'facial', 
    'dress', 'shield', 'tools', 'weapon'
]

LPC_ANIM_MAP = {
    "Walk Cycle (9 Frame)": {"rowStart": 8, "frames": 9},
    "Spellcast (7 Frame)": {"rowStart": 0, "frames": 7},
    "Thrust (8 Frame)": {"rowStart": 4, "frames": 8},
    "Slash (6 Frame)": {"rowStart": 12, "frames": 6},
    "Shoot (13 Frame)": {"rowStart": 16, "frames": 13},
    "Hurt/Die (6 Frame)": {"rowStart": 20, "frames": 6}
}

DIRECTION_MAP = {
    "South (Selatan)": 2,
    "North (Utara)": 0,
    "West (Barat)": 1,
    "East (Timur)": 3
}

SHEET_WIDTH = 832
SHEET_HEIGHT = 1344

BASE_DIR = "spritesheets"

# -----------------------------------------------------------------------------
# FUNGSI MEMBACA FOLDER TEMPATAN
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner="Mengimbas folder spritesheets tempatan...")
def scan_local_spritesheets():
    catalog = {}
    if not os.path.exists(BASE_DIR):
        return catalog

    for root, _, files in os.walk(BASE_DIR):
        for file in files:
            if file.endswith(".png"):
                full_path = os.path.join(root, file)
                # Ambil laluan relatif dari folder spritesheets
                rel_path = os.path.relpath(full_path, BASE_DIR)
                parts = rel_path.split(os.sep)
                
                if len(parts) >= 2:
                    category = parts[0] # Kategori utama (body, hair, torso, etc)
                    display_name = "/".join(parts[1:]) # Sub-path fail PNG
                    
                    if category not in catalog:
                        catalog[category] = {}
                    catalog[category][display_name] = full_path

    return catalog

# -----------------------------------------------------------------------------
# FUNGSI PEMPROSESAN GAMBAR & GIF
# -----------------------------------------------------------------------------
def composite_spritesheet(selected_paths: list) -> Image.Image:
    canvas = Image.new("RGBA", (SHEET_WIDTH, SHEET_HEIGHT), (0, 0, 0, 0))

    for path in selected_paths:
        if path and os.path.exists(path):
            try:
                layer_img = Image.open(path).convert("RGBA")
                if layer_img.size != (SHEET_WIDTH, SHEET_HEIGHT):
                    layer_img = layer_img.resize((SHEET_WIDTH, SHEET_HEIGHT), Image.Resampling.NEAREST)
                canvas = Image.alpha_composite(canvas, layer_img)
            except Exception:
                pass

    return canvas

def extract_frame(sheet: Image.Image, row: int, frame_idx: int) -> Image.Image:
    left = frame_idx * 64
    top = row * 64
    return sheet.crop((left, top, left + 64, top + 64))

def generate_gif(sheet: Image.Image, anim_name: str, direction_idx: int) -> bytes:
    anim_info = LPC_ANIM_MAP[anim_name]
    row = anim_info["rowStart"] if anim_name == "Hurt/Die (6 Frame)" else anim_info["rowStart"] + direction_idx
    frames = []

    for f in range(anim_info["frames"]):
        frame_img = extract_frame(sheet, row, f)
        resized_frame = frame_img.resize((256, 256), Image.Resampling.NEAREST)
        frames.append(resized_frame)

    buf = io.BytesIO()
    if frames:
        frames[0].save(
            buf,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=120,
            loop=0,
            disposal=2
        )
    return buf.getvalue()

# -----------------------------------------------------------------------------
# ANTARAMUKA UTAMA STREAMLIT
# -----------------------------------------------------------------------------
st.title("🎨 Universal LPC Character Generator")
st.caption("Penjana Watak NPC 2D (Mod Tempatan / Offline)")

catalog = scan_local_spritesheets()

if not catalog:
    st.error(f"❌ Folder '{BASE_DIR}' tidak ditemui di dalam repositori anda.")
    st.stop()

with st.sidebar:
    st.header("⚙️ Tetapan Watak")
    
    if st.button("🎲 Rawak (Randomize)", use_container_width=True, type="primary"):
        st.session_state['random_trigger'] = True

    st.markdown("---")

    selected_file_paths = {}
    
    # Susun kategori mengikut hirarki LPC
    sorted_categories = sorted(
        catalog.keys(),
        key=lambda c: LPC_LAYER_ORDER.index(c) if c in LPC_LAYER_ORDER else 99
    )

    for cat in sorted_categories:
        options = ["-- Kosong --"] + sorted(list(catalog[cat].keys()))

        if st.session_state.get('random_trigger', False):
            rand_idx = random.randint(1, len(options) - 1) if random.random() < 0.7 else 0
            st.session_state[f"select_{cat}"] = options[rand_idx]

        selected_val = st.selectbox(
            f"Lapisan: {cat.capitalize()}",
            options=options,
            key=f"select_{cat}"
        )

        if selected_val != "-- Kosong --":
            selected_file_paths[cat] = catalog[cat][selected_val]
        else:
            selected_file_paths[cat] = None

    if 'random_trigger' in st.session_state:
        st.session_state['random_trigger'] = False

# Susun laluan fail mengikut hirarki lapisan LPC
ordered_paths = []
for cat in LPC_LAYER_ORDER:
    if cat in selected_file_paths and selected_file_paths[cat]:
        ordered_paths.append(selected_file_paths[cat])

for cat, path in selected_file_paths.items():
    if cat not in LPC_LAYER_ORDER and path:
        ordered_paths.append(path)

# Paparan Utama
col1, col2 = st.columns([1, 1])

if ordered_paths:
    with col1:
        st.subheader("🎬 Animasi Watak")
        anim_name = st.selectbox("Jenis Animasi:", list(LPC_ANIM_MAP.keys()))
        direction_name = st.selectbox("Arah Pandangan:", list(DIRECTION_MAP.keys()))
        direction_idx = DIRECTION_MAP[direction_name]

        composited_sheet = composite_spritesheet(ordered_paths)
        gif_bytes = generate_gif(composited_sheet, anim_name, direction_idx)

        st.markdown("#### 👁️ Pratonton Live")
        st.image(gif_bytes, caption=f"{anim_name} - {direction_name}", width=256)

    with col2:
        st.subheader("🖼️ Full Spritesheet")
        st.image(composited_sheet, caption="832 x 1344 px", use_container_width=True)

    st.markdown("---")
    st.subheader("📥 Muat Turun")

    dl1, dl2, dl3 = st.columns(3)

    sheet_buf = io.BytesIO()
    composited_sheet.save(sheet_buf, format="PNG")
    dl1.download_button(
        "⬇️ Spritesheet (PNG)",
        data=sheet_buf.getvalue(),
        file_name="npc_spritesheet.png",
        mime="image/png",
        use_container_width=True
    )

    dl2.download_button(
        "⬇️ Animasi (GIF)",
        data=gif_bytes,
        file_name="npc_animation.gif",
        mime="image/gif",
        use_container_width=True
    )

    anim_info = LPC_ANIM_MAP[anim_name]
    row_idx = anim_info["rowStart"] if anim_name == "Hurt/Die (6 Frame)" else anim_info["rowStart"] + direction_idx
    single_frame = extract_frame(composited_sheet, row_idx, 0)
    frame_buf = io.BytesIO()
    single_frame.save(frame_buf, format="PNG")
    dl3.download_button(
        "⬇️ Single Frame 64x64 (PNG)",
        data=frame_buf.getvalue(),
        file_name="npc_frame.png",
        mime="image/png",
        use_container_width=True
    )
else:
    st.info("👈 Sila pilih sekurang-kurangnya satu lapisan (contoh: Body) di sidebar kiri.")