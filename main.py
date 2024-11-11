from difflib import SequenceMatcher
from itertools import combinations
import tkinter as tk
from tkinter import ttk
import subprocess
import threading
import queue
import logging
import re
import nltk
from nltk.util import ngrams
nltk.download('punkt_tab')
from collections import Counter

# Configure logging
logging.basicConfig(
    filename="translator.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

class WhisperRealtimeTranslator:
    def __init__(self, root):
        self.root = root
        self.root.title("Whisper.cpp Realtime Translator")
        self.root.geometry("600x500")
        
        # Input Label
        self.input_label = ttk.Label(self.root, text="Real-Time Translation (Japanese -> English):")
        self.input_label.pack(pady=10)
        
        # Output Text Box
        self.output_text = tk.Text(self.root, wrap=tk.WORD, state=tk.DISABLED, height=15, width=70)
        self.output_text.pack(pady=10)
        
        # Desktop Stream Selector
        self.source_label = ttk.Label(self.root, text="Select Audio Source:")
        self.source_label.pack(pady=5)
        
        self.source_combobox = ttk.Combobox(self.root, state="readonly")
        self.source_combobox['values'] = ["Desktop Audio", "Microphone"]
        self.source_combobox.current(0)  # Default to "Desktop Audio"
        self.source_combobox.pack(pady=5)
        
        # Status Label
        self.status_label = ttk.Label(self.root, text="Status: Idle", foreground="white")
        self.status_label.pack(pady=10)
        
        # Control Buttons
        self.button_frame = ttk.Frame(self.root)
        self.button_frame.pack(pady=10)
        
        self.start_button = ttk.Button(self.button_frame, text="Start Translation", command=self.start_translation)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(self.button_frame, text="Stop Translation", command=self.stop_translation, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.clear_button = ttk.Button(self.button_frame, text="Clear", command=self.clear_output)
        self.clear_button.pack(side=tk.LEFT, padx=5)
        
        # Whisper subprocess and threading components
        self.translator_process = None
        self.translation_thread = None
        self.translation_queue = queue.Queue()
        self.running = False
        self.WHISPER_ROOT = "/Users/hirunkulphimsiri/Documents/programming/project/whisper.cpp"
        self.hallucinated_tokens = ["Thank you.", "Thank you for watching.", "Thank you very much.", "Thank you!", "Thank you for watching!", "Thank you very much!"]

    def update_status(self, status, color="white"):
        """Update the status label."""
        self.status_label.config(text=f"Status: {status}", foreground=color)

    def start_translation(self):
        """Start the Whisper.cpp process for translation."""
        logging.info("Starting translation process.")
        self.update_status("Translating...", "green")
        self.running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        self.translation_thread = threading.Thread(target=self.run_whisper_cpp, daemon=True)
        self.translation_thread.start()
        self.update_translation_output()

    def stop_translation(self):
        """Stop the Whisper.cpp process."""
        logging.info("Stopping translation process.")
        self.update_status("Idle", "white")
        self.running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        if self.translator_process:
            self.translator_process.terminate()
            self.translator_process = None

    def clear_output(self):
        """Clear the output text box."""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.DISABLED)

    def detect_repetition(self, line, n=3, threshold=0.5):
        """
        Detect if the line contains repetitive phrases.
        
        Parameters:
        - line (str): The input text line to check for repetition.
        - n (int): The number of repetitions to consider as repetitive.
        - threshold (float): The similarity threshold to consider two sentences as identical (0-1).
        
        Returns:
        - bool: True if repetitive phrases are detected, False otherwise.
        """
        # Tokenize the line into sentences
        sentences = nltk.sent_tokenize(line)
        log = {"line": line, "sentences": sentences, "n": n, "threshold": threshold, "repetition": False}

        # Generate all unique sentence pairs
        sentence_pairs = combinations(sentences, 2)
        
        # Count repetitions based on similarity
        repetition_count = sum(
            1 for s1, s2 in sentence_pairs if SequenceMatcher(None, s1, s2).ratio() >= threshold
        )
        
        # Log and return based on repetition count
        log["repetition"] = repetition_count >= n
        logging.debug(log)
        return log["repetition"]

    def clean_translation_line(self, line):
        """Clean unwanted escape sequences from the translation line."""
        line = line.strip()
        cleaned_line = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', line)  # Remove ANSI escape codes
        # Remove if the line start with ( and end with )
        if cleaned_line.startswith("(") and cleaned_line.endswith(")"):
            return None
        # Hallucination detection
        if any(token in cleaned_line for token in self.hallucinated_tokens):
            return None
        # Single Line Reperttion Detection
        if self.detect_repetition(cleaned_line):
                    logging.debug(f"Repetition detected: {cleaned_line}")
                    return None
        
        return cleaned_line

    def run_whisper_cpp(self):
        """Run Whisper.cpp in real time and capture output."""
        try:
            source = self.source_combobox.get()
            logging.info(f"Selected audio source: {source}")
            
            # Simulate audio source configuration
            if source == "Desktop Audio":
                audio_source = "desktop-audio"
            else:
                audio_source = "microphone"
            
            # Whisper.cpp subprocess
            cmd = [f"{self.WHISPER_ROOT}/stream", "-m", f"{self.WHISPER_ROOT}/models/ggml-large-v2-q5_0.bin", "-l", "ja", "-tr", "-t", "6", "--length", "30000", "-vth", "0.6"]
            logging.debug(
                f'Excecute: {" ".join(cmd)}'
            )
            self.translator_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            logging.info("Whisper.cpp process started.")
            
            for line in iter(self.translator_process.stdout.readline, ''):
                if not self.running:
                    break
                cleaned_line = self.clean_translation_line(line)
                if cleaned_line:  # Ignore empty or noise lines
                    logging.debug(f"Translation line: {cleaned_line}")
                    self.translation_queue.put(cleaned_line)
        except Exception as e:
            error_message = f"Error: {str(e)}"
            logging.error(error_message)
            self.translation_queue.put(error_message)
        finally:
            self.running = False
            self.update_status("Idle", "white")

    def update_translation_output(self):
        """Update the GUI output text box with translations."""
        try:
            while not self.translation_queue.empty():
                line = self.translation_queue.get_nowait()
                if line:
                    self.output_text.config(state=tk.NORMAL)
                    # Get the last line in the text widget
                    last_index = self.output_text.index("end-2c linestart")
                    last_line = self.output_text.get(last_index, "end-1c").strip()
                    
                    # Check if the current line contains the last line as a substring
                    if last_line and last_line in line:
                        # Delete the last line and replace it with the new line
                        self.output_text.delete(last_index, "end-1c")
                        # Log the deletion
                        logging.debug(f"Deleted: {last_line} due to repetition in: {line}")
                    
                    # Add the new line to the output text
                    self.output_text.insert(tk.END, f"{line}\n")
                    self.output_text.see(tk.END)
                    self.output_text.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        finally:
            if self.running:
                self.root.after(100, self.update_translation_output)

def main():
    root = tk.Tk()
    app = WhisperRealtimeTranslator(root)
    root.mainloop()

if __name__ == "__main__":
    main()
