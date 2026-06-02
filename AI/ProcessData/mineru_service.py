import os
import requests
import time

MAX_CONNECTION_ERRORS = 5
MAX_POLL_ATTEMPTS     = 120  # 40 × 15s = 10 phút tối đa / lần upload

class MinerU:
    def __init__(self):
        self.api_url = os.getenv("COLAB_API_URL")
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ai_dir = os.path.dirname(current_dir)
        self.cache_dir = os.path.join(ai_dir, "data", "processed_text")
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def _upload_and_poll(self, pdf_path):
        """
        Upload 1 file PDF lên Colab và poll đến khi xong.
        Colab tự tách PDF nên không cần tách ở local nữa.
        """
        file_name = os.path.basename(pdf_path)
        cache_path = os.path.join(self.cache_dir, file_name.replace(".pdf", ".txt"))

        if os.path.exists(cache_path):
            print(f"Cache hit: {file_name}")
            with open(cache_path, "r", encoding="utf-8") as f:
                return f.read()

        try:
            print(f"Đang tải lên Colab: {file_name}")

            if not self.api_url:
                return "LỖI: Biến COLAB_API_URL đang trống"

            headers = {"ngrok-skip-browser-warning": "true"}

            with open(pdf_path, 'rb') as f:
                response = requests.post(
                    f"{self.api_url}/convert",
                    files={'file': f},
                    headers=headers,
                    timeout=120  # file gốc lớn hơn, timeout upload dài hơn
                )

            if response.status_code != 200:
                return f"LỖI API {response.status_code}"

            file_id = response.json().get("file_id")
            print(f"Đã tải lên, Colab đang xử lý: {file_name}")

            connection_errors = 0
            poll_attempts = 0

            while poll_attempts < MAX_POLL_ATTEMPTS:
                time.sleep(15)
                poll_attempts += 1
                elapsed_m = (poll_attempts * 15) // 60
                remaining  = (MAX_POLL_ATTEMPTS - poll_attempts) * 15 // 60

                try:
                    res = requests.get(
                        f"{self.api_url}/result/{file_id}",
                        headers=headers,
                        timeout=30
                    )
                    connection_errors = 0

                    if res.status_code == 200:
                        status_data = res.json()
                        status = status_data.get("status")

                        if status == "done":
                            clean_text = status_data.get("text")
                            with open(cache_path, "w", encoding="utf-8") as f:
                                f.write(clean_text)
                            print(f"✅ Hoàn thành: {file_name}")
                            return clean_text

                        elif status == "error":
                            return f"LỖI COLAB: {status_data.get('message')}"

                        else:
                            print(f"  ⏳ [{elapsed_m} phút] Đang xử lý {file_name}... (còn tối đa {remaining} phút)")

                    else:
                        connection_errors += 1
                        print(f"  Đường truyền gián đoạn ({connection_errors}/{MAX_CONNECTION_ERRORS})")
                        if connection_errors >= MAX_CONNECTION_ERRORS:
                            return "LỖI: Mất kết nối Colab quá nhiều lần."

                except requests.exceptions.ConnectionError:
                    connection_errors += 1
                    print(f"  Mất kết nối ({connection_errors}/{MAX_CONNECTION_ERRORS})")
                    if connection_errors >= MAX_CONNECTION_ERRORS:
                        return "LỖI: Colab bị kill hoặc mất mạng."

            total_waited = MAX_POLL_ATTEMPTS * 15 // 60
            return f"LỖI TIMEOUT: {file_name} xử lý quá {total_waited} phút. Restart Colab và thử lại."

        except requests.exceptions.ConnectionError:
            return f"LỖI KẾT NỐI: Không thể gọi tới {self.api_url}"
        except Exception as e:
            return f"LỖI HỆ THỐNG: {str(e)}"

    def process(self, pdf_path):
        """
        Hàm chính: upload file gốc lên Colab.
        Colab tự tách PDF bằng PyMuPDF của nó → tránh lỗi xref cross-version.
        """
        file_name = os.path.basename(pdf_path)

        final_cache = os.path.join(
            self.cache_dir,
            file_name.replace(".pdf", "_full.txt")
        )
        if os.path.exists(final_cache):
            print(f"Cache tổng hit: {file_name}")
            with open(final_cache, "r", encoding="utf-8") as f:
                return f.read()

        # Upload file gốc — Colab tự tách
        text = self._upload_and_poll(pdf_path)
        if text.startswith("LỖI"):
            return text

        with open(final_cache, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Đã cache tổng: {file_name}")

        return text
