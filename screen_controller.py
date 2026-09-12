
import pyautogui, mss, cv2, numpy as np, base64, json, sys
from pathlib import Path

class ScreenController:
    def __init__(self):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1
        self.sct = mss.mss()
    
    def screenshot(self, region=None):
        img = self.sct.grab(region or self.sct.monitors[1])
        arr = np.array(img)[:, :, :3]
        _, buf = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return base64.b64encode(buf).decode()
    
    def click(self, x, y): pyautogui.click(x, y); return {"ok": True, "x": x, "y": y}
    def type_text(self, text): pyautogui.write(text); return {"ok": True}
    def hotkey(self, *keys): pyautogui.hotkey(*keys); return {"ok": True}
    def scroll(self, clicks): pyautogui.scroll(clicks); return {"ok": True}
    def find_on_screen(self, template_path):
        scr = pyautogui.screenshot()
        tmpl = cv2.imread(template_path)
        if tmpl is None: return {"found": False}
        res = cv2.matchTemplate(np.array(scr), tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_v, _, max_l = cv2.minMaxLoc(res)
        return {"found": max_v > 0.8, "x": max_l[0], "y": max_l[1], "confidence": float(max_v)}

if __name__ == "__main__":
    sc = ScreenController()
    if len(sys.argv) > 1 and sys.argv[1] == "screenshot":
        img_b64 = sc.screenshot()
        print(json.dumps({"ok": True, "tool": "screen_capture", "image_base64": img_b64, "format": "jpeg"}))
    else:
        print(json.dumps({"status": "ready", "screen_size": list(pyautogui.size())}))
