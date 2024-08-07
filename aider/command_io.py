import sys
import json
import select

from aider.io import InputOutput

class CommandIO(InputOutput):
    def __init__(
        self,
        yes=False,
        input_history_file=None,
        chat_history_file=None,
        encoding="utf-8",
        dry_run=False,
        llm_history_file=None,
    ):
        super().__init__(
            input_history_file=input_history_file,
            chat_history_file=chat_history_file,
            encoding=encoding,
            dry_run=dry_run,
            llm_history_file=llm_history_file,
        )

        self.yes = yes
        self.input_buffer = ""
        self.input_decoder = json.JSONDecoder()

    def get_input(self, root, rel_fnames, addable_rel_fnames, commands):
        obj = self.get_command()
        
        if obj:
            send, inp = self.run_command(obj, commands)

            if send:
                return inp
        
        return ""
    
    def get_command(self, wait = True):
        need_input = False
        
        while True:
            try:
                input_chunk = sys.stdin.read()
                
                if not input_chunk and need_input:
                    if wait:
                        select.select([sys.stdin], [], [], 1)
                    else:
                        return None
                    
                if input_chunk:
                    self.input_buffer += input_chunk

                while self.input_buffer:
                    try:
                        obj, idx = self.input_decoder.raw_decode(self.input_buffer)
                        self.input_buffer = self.input_buffer[idx:].lstrip()
                        return obj
                        
                    except json.JSONDecodeError:
                        # If JSON is not complete, break
                        need_input = True
                        break

            except KeyboardInterrupt:
                break
        
        return ""
    
    #return Send, Input
    def run_command(self, obj, commands):
        cmd_list=commands.get_commands()
        
        cmd = obj.get('cmd')
        
        if cmd in cmd_list:
            return True, f"/{cmd} {' '.join(obj.get('value'))}"
        elif cmd == 'user':
            return True, obj.get('value')
        
        return False, ""
        
    def user_input(self, inp, log_only=True):
        msg = {
            "cmd": "user",
            "value": inp
        }
        print(json.dumps(msg))
        return
        
    def confirm_ask(self, question, default="y", send=False):
        msg = {
            "cmd": "ask",
            "value": question,
            "default": default
        }
        print(json.dumps(msg))
        
        obj = self.get_command()
        
        cmd = obj.get('cmd')
        res = "no"
        
        if cmd == "response":
            res = obj.get('value')

        hist = f"{question.strip()} {res.strip()}"
        self.append_chat_history(hist, linebreak=True, blockquote=True)
                
        return res.strip().lower().startswith("y")

    def prompt_ask(self, question, default=None):
        res = self.confirm_ask(question, default)
    
    def tool_error(self, message="", strip=True):
        super().tool_error(message, strip)
                        
        msg = {
            "cmd": "error",
            "value": message
        }
        print(json.dumps(msg))

    def tool_output(self, *messages, log_only=False):
        super().tool_output(*messages, log_only=log_only)
            
        msg = {
            "cmd": "output",
            "value": " ".join(messages)
        }
        print(json.dumps(msg))
