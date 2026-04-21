import os 
import requests 
import time 

class  MarkerService:
    def __init__(self):
        self.api_url = os.getenv("COLAB_API_URL")
        # Thư mục lưu Cache -> ko bao giờ phải chạy lại 1 file 2 lần
        self.cache_dir = os.path.join("data", "processed_text")
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def process(self, pdf_path):  
        """
        Nhận pdf_path từ read_data truyền sang.
        """
        file_name = os.path.basename(pdf_path)
        cache_path = os.path.join(self.cache_dir, file_name.replace(".pdf", ".txt"))

        # kiểm tra lưu trữ, tiết kết token gọi t4
        if os.path.exists(cache_path):
            print(f"Đã có bản sạch trong kho. Đang lấy ra")
            with open(cache_path, "r", encoding="utf-8") as f:
                return f.read()
        
        # nếu chưa có, gửi input lên tesla
        try:
            print(f"Đang tải tài liệu lên Tesla")
            
            if not self.api_url:
                return "LỖI: Biến COLAB_API_URL đang trống"

            headers = {"ngrok-skip-browser-warning": "true"}
            
            with open(pdf_path, 'rb') as f:
                files = {'file': f}
                # Gửi file lên
                response = requests.post(f"{self.api_url}/convert", files=files, headers=headers, timeout=60)
            
            if response.status_code == 200:
                file_id = response.json().get("file_id")
                print(f"Tải lên hoàn tất, Tesla T4 đang xử lí")
                
                # VÒNG LẶP HỎI THĂM (15s hỏi 1 lần)
                while True:
                    time.sleep(15)
                    res = requests.get(f"{self.api_url}/result/{file_id}", headers=headers, timeout=30)
                    
                    if res.status_code == 200:
                        status_data = res.json()
                        status = status_data.get("status")
                        
                        if status == "done":
                            clean_text = status_data.get("text")
                            with open(cache_path, "w", encoding="utf-8") as f:
                                f.write(clean_text)
                            print(f"Succes. Đã hoàn thành {file_name}!")
                            return clean_text
                            
                        elif status == "error":
                            error_msg = f"Lỗi colab {status_data.get('message')}"
                            print(error_msg)
                            return error_msg
                            
                        else:
                            print("Vui lòng đợi thêm 15s")
                    else:
                        print(" Đường truyền gián đoạn, đang thử lại")
            else:
                return f"LỖI API {response.status_code}"
                
        # Bắt các lỗi mất mạng, chưa bật server
        except requests.exceptions.ConnectionError:
            error_msg = f"LỖI KẾT NỐI: Không thể gọi tới {self.api_url}. Xem lại đường dẫn trong env"
            print(error_msg)
            return error_msg
            
        # Bắt các lỗi dị thường khác
        except Exception as e:
            error_msg = f"LỖI HỆ THỐNG: {str(e)}"
            print(error_msg)
            return error_msg