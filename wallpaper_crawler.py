import os
import re
import requests
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


class WallpaperCrawler:
    def __init__(self, download_dir):
        self.download_dir = Path(download_dir)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def crawl(self, urls):
        """
        从给定的URL列表爬取壁纸图片
        """
        success_count = 0

        for url in urls:
            try:
                # 获取网页内容
                response = self.session.get(url, timeout=10)
                response.raise_for_status()

                # 解析HTML
                soup = BeautifulSoup(response.text, 'html.parser')

                # 查找所有图片
                images = soup.find_all('img')

                for img in images:
                    # 获取图片URL
                    img_url = img.get('src') or img.get('data-src')
                    if not img_url:
                        continue

                    # 转换为绝对URL
                    img_url = urljoin(url, img_url)

                    # 下载图片
                    if self.download_image(img_url):
                        success_count += 1

            except Exception as e:
                print(f"爬取 {url} 时出错: {str(e)}")
                continue

        return success_count

    def download_image(self, img_url):
        """
        下载单张图片
        """
        try:
            # 获取图片
            response = self.session.get(img_url, stream=True, timeout=10)
            response.raise_for_status()

            # 检查是否为图片
            content_type = response.headers.get('content-type', '')
            if 'image' not in content_type:
                return False

            # 从URL提取文件名
            parsed_url = urlparse(img_url)
            filename = os.path.basename(parsed_url.path)

            # 如果没有有效的文件名，生成一个
            if not filename or '.' not in filename:
                filename = f"wallpaper_{hash(img_url)}.jpg"

            # 确保文件名是安全的
            filename = self.sanitize_filename(filename)

            # 保存路径
            save_path = self.download_dir / filename

            # 如果文件已存在，跳过
            if save_path.exists():
                return False

            # 下载文件
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"下载成功: {filename}")
            return True

        except Exception as e:
            print(f"下载图片失败 {img_url}: {str(e)}")
            return False

    def sanitize_filename(self, filename):
        """
        确保文件名是安全的
        """
        # 移除非法字符
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)

        # 限制文件名长度
        if len(filename) > 100:
            name, ext = os.path.splitext(filename)
            filename = name[:100 - len(ext)] + ext

        return filename