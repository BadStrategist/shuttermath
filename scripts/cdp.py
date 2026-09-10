#!/usr/bin/env python3
"""Extended CDP driver for isolated ShutterMath Chrome (port 9225).
Actions: nav URL | dump | js EXPR | jsx EXPR(JSON) | wait MS | qsel SEL | title | url
         fill SEL VAL | click SEL | setv SEL VAL(select) | clickxy X Y
Reusable as module: from cdp import page
"""
import json, sys, asyncio, urllib.request
import websockets

PORT = 9225

def get_page_target():
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json") as r:
        for t in json.load(r):
            if t["type"] == "page":
                return t

async def _ws():
    return await websockets.connect(get_page_target()["webSocketDebuggerUrl"], max_size=100*1024*1024)

class Page:
    def __init__(self, ws):
        self.ws = ws; self._id = 0
    async def cmd(self, method, params=None):
        self._id += 1; mid = self._id
        await self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg: raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})
    async def ev(self, expr):
        r = await self.cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        return r.get("result", {})
    async def evx(self, expr):
        r = await self.ev("JSON.stringify(" + expr + ")")
        return json.loads(r.get("value", "null"))
    async def nav(self, url):
        await self.cmd("Page.navigate", {"url": url})
    async def title(self):
        return (await self.ev("document.title")).get("value")
    async def close(self):
        await self.ws.close()

async def _run(action, args):
    page = Page(await _ws())
    out = None
    try:
        if action == "nav":
            await page.nav(args[0])
        elif action == "wait":
            await asyncio.sleep(float(args[0])/1000.0)
        elif action == "title":
            out = await page.title()
        elif action == "url":
            out = (await page.ev("location.href")).get("value")
        elif action == "dump":
            out = (await page.ev("document.body ? document.body.innerText : ''")).get("value")
        elif action == "js":
            r = await page.ev(args[0]); out = r.get("value", r.get("description", ""))
        elif action == "jsx":
            out = await page.evx(args[0])
        elif action == "qsel":
            out = await page.evx("Array.from(document.querySelectorAll(%s)).map(e=>({tag:e.tagName,type:e.type||'',name:e.name||'',id:e.id||'',cls:e.className||'',val:e.value||'',ph:e.placeholder||'',href:e.href||'',text:(e.innerText||'').trim().slice(0,60)}))" % json.dumps(args[0]))
        elif action == "fill":
            sel, val = args[0], args[1]
            out = await page.ev("(()=>{const e=document.querySelector(%s);if(!e)return 'NOELEM';e.focus();const s=Object.getOwnPropertyDescriptor(e.__proto__||HTMLInputElement.prototype,'value').set; s?s.call(e,%s):(e.value=%s); e.dispatchEvent(new Event('input',{bubbles:true})); e.dispatchEvent(new Event('change',{bubbles:true})); return 'OK';})()" % (json.dumps(sel), json.dumps(val), json.dumps(val)))
        elif action == "click":
            out = await page.ev("(()=>{const e=document.querySelector(%s);if(!e)return 'NOELEM';e.click();return 'OK';})()" % json.dumps(args[0]))
        elif action == "clickxy":
            x, y = float(args[0]), float(args[1])
            await page.cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
            await page.cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
            out = "clicked"
        elif action == "setv":
            sel, val = args[0], args[1]
            out = await page.ev("(()=>{const e=document.querySelector(%s);if(!e)return 'NOELEM';e.value=%s;e.dispatchEvent(new Event('change',{bubbles:true}));return 'OK';})()" % (json.dumps(sel), json.dumps(val)))
    finally:
        await page.close()
    if out is not None:
        if isinstance(out, str):
            print(out)
        else:
            print(json.dumps(out, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(_run(sys.argv[1], sys.argv[2:])))
