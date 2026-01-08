"""Quick test script to verify Gradio works"""
import sys
print("Python version:", sys.version, flush=True)
print("Starting Gradio import...", flush=True)

import gradio as gr
print("Gradio imported successfully!", flush=True)

from pooling_calculator import __version__
print(f"Pooling Calculator version: {__version__}", flush=True)

print("Building simple app...", flush=True)

def greet(name):
    return f"Hello {name}!"

demo = gr.Interface(fn=greet, inputs="text", outputs="text")

print("App built successfully!", flush=True)
print("Launching on http://127.0.0.1:7860", flush=True)

demo.launch(server_name="127.0.0.1", server_port=7860, share=False)
