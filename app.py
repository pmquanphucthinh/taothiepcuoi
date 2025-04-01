import logging
import io
import base64
from PIL import Image, ImageDraw, ImageFont
from flask import Flask, request, render_template, send_file

# --- Cấu hình (Giữ nguyên hoặc điều chỉnh nếu cần) ---
IMAGE_PATH = 'thiep.png'
FONT_PATH = 'DancingScript-Bold.ttf'
FONT_SIZE = 100
TEXT_POSITION = (1140, 625) # Vị trí TRUNG TÂM của khu vực chữ
TEXT_COLOR = '#ff5757'  # Mã màu hex
TEXT_ANGLE = 4 # Góc nghiêng (độ)
BOX_WIDTH = 5000   # Chiều rộng của khu vực căn giữa (đảm bảo đủ rộng)
BOX_HEIGHT = 300  # Chiều cao của khu vực căn giữa

# --- Thiết lập Logging (Tùy chọn, hữu ích cho gỡ lỗi trên Vercel) ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Khởi tạo Flask App ---
app = Flask(__name__)

# --- Hàm chuyển đổi mã màu hex sang RGB (Giữ nguyên) ---
def hex_to_rgb(hex_color):
    """Chuyển đổi mã màu hex thành tuple RGB."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

# --- Hàm xử lý ảnh (Giữ nguyên logic cốt lõi) ---
def add_text_to_image(text_to_add):
    """Mở ảnh gốc, thêm text vào và trả về đối tượng BytesIO chứa ảnh PNG."""
    try:
        # Mở ảnh gốc
        img = Image.open(IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(img)

        # Load font chữ
        try:
            font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        except IOError:
            logger.error(f"Lỗi: Không tìm thấy file font tại '{FONT_PATH}'. Dùng font mặc định.")
            # Trên serverless, việc dùng font mặc định có thể không ổn định
            # Tốt nhất là đảm bảo font có trong thư mục dự án
            return None # Trả về None nếu không load được font chính

        # Lấy kích thước chữ
        bbox = draw.textbbox((0,0), text_to_add, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        center_x, center_y = TEXT_POSITION # Đổi tên biến cho rõ nghĩa

        # Tạo một ảnh trong suốt mới cho text (kích thước đủ lớn)
        # Kích thước này phải đủ lớn để chứa text sau khi xoay
        # Ước lượng kích thước cần thiết (có thể cần điều chỉnh)
        diag = int((text_width**2 + text_height**2)**0.5) + 20 # Thêm padding
        text_img_size = max(diag, BOX_WIDTH, BOX_HEIGHT) # Lấy kích thước lớn nhất có thể
        text_img = Image.new('RGBA', (text_img_size, text_img_size), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_img)

        # Tính toán vị trí để vẽ chữ vào TRUNG TÂM của ảnh text_img
        text_img_center_x = text_img_size // 2
        text_img_center_y = text_img_size // 2
        text_x = text_img_center_x - text_width // 2
        text_y = text_img_center_y - text_height // 2

        # Chuyển đổi mã màu hex sang RGB
        rgb_color = hex_to_rgb(TEXT_COLOR)

        # Vẽ chữ vào ảnh trong suốt
        text_draw.text((text_x, text_y), text_to_add, fill=rgb_color, font=font)

        # Xoay ảnh chứa chữ quanh tâm của nó
        rotated_text_img = text_img.rotate(TEXT_ANGLE, expand=True, center=(text_img_center_x, text_img_center_y))

        # Tính toán vị trí để dán ảnh đã xoay lên ảnh gốc
        # Vị trí dán là vị trí TRUNG TÂM mong muốn trừ đi một nửa kích thước của ảnh đã xoay
        rotated_width, rotated_height = rotated_text_img.size
        paste_x = center_x - rotated_width // 2
        paste_y = center_y - rotated_height // 2

        # Dán ảnh đã xoay lên ảnh gốc sử dụng mask của chính nó để giữ độ trong suốt
        img.paste(rotated_text_img, (int(paste_x), int(paste_y)), rotated_text_img)

        # Lưu ảnh đã chỉnh sửa vào bộ nhớ đệm (bytes buffer)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0) # Đưa con trỏ về đầu buffer để đọc

        return img_byte_arr

    except FileNotFoundError:
        logger.error(f"Lỗi: Không tìm thấy file ảnh gốc tại '{IMAGE_PATH}'")
        return None
    except Exception as e:
        logger.error(f"Lỗi không xác định khi xử lý ảnh: {e}")
        return None

# --- Route cho trang chính và xử lý POST ---
@app.route('/', methods=['GET', 'POST'])
def index():
    image_data_uri = None
    error_message = None
    user_text_input = ""

    if request.method == 'POST':
        user_text = request.form.get('user_text')
        user_text_input = user_text # Lưu lại để hiển thị trên form
        logger.info(f"Nhận được text: '{user_text}'")

        if not user_text:
            error_message = "Vui lòng nhập tên hoặc lời chúc."
        else:
            # Gọi hàm xử lý ảnh
            image_bytes_io = add_text_to_image(user_text)

            if image_bytes_io:
                try:
                    # Chuyển đổi ảnh bytes thành Base64 để nhúng vào HTML
                    img_base64 = base64.b64encode(image_bytes_io.read()).decode('utf-8')
                    image_data_uri = f"data:image/png;base64,{img_base64}"
                    logger.info("Đã tạo ảnh và chuyển thành data URI.")
                except Exception as e:
                    logger.error(f"Lỗi khi chuyển đổi ảnh sang Base64: {e}")
                    error_message = "Đã có lỗi xảy ra khi chuẩn bị hiển thị ảnh."
            else:
                # Lỗi xảy ra trong hàm add_text_to_image
                error_message = "Xin lỗi, không thể tạo ảnh. Vui lòng kiểm tra lại hoặc thử lại sau."

    # Render template HTML, truyền dữ liệu ảnh (nếu có) và lỗi (nếu có)
    return render_template('index.html',
                           image_data=image_data_uri,
                           error=error_message,
                           user_text_input=user_text_input)

# --- Chạy App (Chủ yếu cho local development, Vercel sẽ dùng cách khác) ---
# if __name__ == '__main__':
#     app.run(debug=True) # Bật debug mode khi chạy local
