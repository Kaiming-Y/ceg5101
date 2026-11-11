#!/usr/bin/env python3
"""Open a run's overview figure in a window (needs a display: VM desktop, or ssh -Y with an X server).

usage: python3 code/demo/show_figure.py <results/run-dir> [fig4_overview.png]
"""
import os
import sys
import tkinter as tk

out = sys.argv[1]
name = sys.argv[2] if len(sys.argv) > 2 else 'fig4_overview.png'
path = os.path.join(out, 'figures', name)
root = tk.Tk()
root.title(name)
img = tk.PhotoImage(file=path)
sw, sh = root.winfo_screenwidth(), root.winfo_screenheight() - 80
k = max(1, -(-img.width() // sw), -(-img.height() // sh))      # integer shrink factor so it fits
if k > 1:
    img = img.subsample(k, k)
tk.Label(root, image=img).pack()
root.bind('<Escape>', lambda e: root.destroy())
root.bind('q', lambda e: root.destroy())
root.mainloop()
