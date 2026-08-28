import os
import random
import io
import requests
from PIL import Image
import streamlit as st

# -----------------------------------------------------------------------------
# KONFIGURASI HALAMAN STREAMLIT
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="LPC Character Generator",
    page_icon="🎨",
    layout="wide"
)

# -----------------------------------------------------------------------------
# KONFIGURASI LPC & ANIMASI
# -----------------------------------------------------------------------------
LPC_LAYER_ORDER = [
    'body', 'head', 'headwear', 'hair', 'arms', 'torso', 
    'legs', 'feet', 'tools', 'weapons'
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

REPO_TREE_URL = "https://api.github.com/repos/mamaiv3/Universal-LPC-Spritesheet-Character-Generator/git/trees/master?recursive=1"
RAW_BASE_URL = "https://raw.githubusercontent.com/mamaiv3/Universal-LPC-Spritesheet-Character-Generator/master/"

# -----------------------------------------------------------------------------
# AMBIL KATALOG FAIL DARI REPOSITORI GITHUB (1 CALL SAHAJA)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner="Memuat naik katalog fail dari GitHub Repo...")
def fetch_repo_catalog():
    catalog = {}
    headers = {"User-Agent": "StreamlitApp"}
    
    # Gunakan token jika dimasuk dalam Streamlit Secrets (pilihan)
    if "GITHUB_TOKEN" in st.secrets:
        headers["Authorization"] = f"token {st.secrets['GITHUB_TOKEN']}"

    try:
        res = requests.get(REPO_TREE_URL, headers=headers, timeout=15)
        res.raise_for_status()
        tree_data = res.json().get("tree", [])

        for item in tree_data:
            path = item.get("path", "")
            if path.startswith("sheet_definitions/") and path.endswith(".png"):
                parts = path.split("/")
                if len(parts) >= 3:
                    cat = parts[1]  # Kategori contoh: body, hair, torso
                    file_name = "/".join(parts[2:]) # Sub-path fail PNG
                    raw_url = RAW_BASE_URL + path

                    if cat not in catalog:
                        catalog[cat] = {}
                    catalog[cat][file_name] = raw_url

    except Exception as e:
        st.error(f"Gagal membaca repositori: {e}")
        
    return catalog

@st.cache_data(show_spinner=False)
def download_image_bytes(url: str):
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return res.content
    except Exception:
        pass
    return None

# -----------------------------------------------------------------------------
# FUNGSI PEMPROSESAN GAMBAR & GIF
# -----------------------------------------------------------------------------
def composite_spritesheet(selected_urls: list) -> Image.Image:
    canvas = Image.new("RGBA", (SHEET_WIDTH, SHEET_HEIGHT), (0, 0, 0, 0))

    for url in selected_urls:
        if url:
            img_bytes = download_image_bytes(url)
            if img_bytes:
                try:
                    layer_img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
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
st.caption("Direka khas untuk mencipta Spritesheet NPC 2D daripada Repositori LPC")

catalog = fetch_repo_catalog()

if not catalog:
    st.warning("⚠️ Tiada aset dijumpai. Sila semak semula sambungan internet atau kuota GitHub API.")
    st.stop()

with st.sidebar:
    st.header("⚙️ Tetapan Watak")
    
    if st.button("🎲 Rawak (Randomize)", use_container_width=True, type="primary"):
        st.session_state['random_trigger'] = True

    st.markdown("---")

    selected_urls = {}
    
    # Susun mengikut hirarki LPC
    sorted_categories = sorted(
        catalog.keys(),
        key=lambda c: LPC_LAYER_ORDER.index(c) if c in LPC_LAYER_ORDER else 99
    )

    for cat in sorted_categories:
        options = ["-- Kosong --"] + list(catalog[cat].keys())

        if st.session_state.get('random_trigger', False):
            # 80% peluang pilih item rawak
            rand_idx = random.randint(1, len(options) - 1) if random.random() < 0.8 else 0
            st.session_state[f"select_{cat}"] = options[rand_idx]

        selected_val = st.selectbox(
            f"Lapisan: {cat.capitalize()}",
            options=options,
            key=f"select_{cat}"
        )

        if selected_val != "-- Kosong --":
            selected_urls[cat] = catalog[cat][selected_val]
        else:
            selected_urls[cat] = None

    if 'random_trigger' in st.session_state:
        st.session_state['random_trigger'] = False

# Susun URL mengikut urutan lapisan LPC yang betul
ordered_urls = []
for cat in LPC_LAYER_ORDER:
    if cat in selected_urls and selected_urls[cat]:
        ordered_urls.append(selected_urls[cat])

for cat, url in selected_urls.items():
    if cat not in LPC_LAYER_ORDER and url:
        ordered_urls.append(url)

# Paparan Utama
col1, col2 = st.columns([1, 1])

if ordered_urls:
    with col1:
        st.subheader("🎬 Animasi Watak")
        anim_name = st.selectbox("Jenis Animasi:", list(LPC_ANIM_MAP.keys()))
        direction_name = st.selectbox("Arah Pandangan:", list(DIRECTION_MAP.keys()))
        direction_idx = DIRECTION_MAP[direction_name]

        composited_sheet = composite_spritesheet(ordered_urls)
        gif_bytes = generate_gif(composited_sheet, anim_name, direction_idx)

        st.markdown("#### 👁️ Pratonton Live")
        st.image(gif_bytes, caption=f"{anim_name} - {direction_name}", width=256)

    with col2:
        st.subheader("🖼️ Full Spritesheet")
        st.image(composited_sheet, caption="832 x 1344 px", use_column_width=True)

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
    st.info("👈 Sila pilih sekurang-kurangnya satu lapisan (contoh: Body) di menu sidebar kiri.")