import inspect
import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from typing import List, Dict, Any, Tuple
from pathlib import Path

load_dotenv()

##print(os.environ["OPENAI_API_KEY"])

openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SYSTEM_PROMPT = """
你是一个乐于助人的编程助手，你的目标是协助完成编程任务。
你可以访问一系列可执行的工具。以下是你可访问的工具：

{tool_list_str}

当你想要使用工具时，请精确回复一行，格式如下：'tool: TOOL_NAME({JSON_ARGS})'，不要包含其他任何内容。
请使用带双引号的紧凑单行 JSON。在收到 tool_result(...) 消息后，继续执行任务。
如果不需要工具，请正常回复。
"""

YOU_COLOR = "\u001b[94m"
ASSISTANT_COLOR = "\u001b[93m"
RESET_COLOR = "\u001b[0m"

def resolve_abs_path(path_str: str) -> Path:
    """
    将输入的路径字符串（相对路径或绝对路径）转换为标准的绝对路径 Path 对象。
    示例: file.py -> /Users/you/project/file.py
    
    :param path_str: 传入的路径字符串
    :return: 转换后的绝对路径 Path 对象
    """
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = (path.cwd() / path).resolve()
    return path

def read_file_tool(filename: str) -> Dict[str, Any]:
    """
    获取用户提供的文件的完整内容。
    :param filename: 要读取的文件名。
    :return: 包含文件路径和文件内容的字典。
    """
    # 将传入的文件名/相对路径解析为标准的绝对路径
    full_path = resolve_abs_path(filename)
    print(full_path)
    
    # 以只读模式打开文件并读取其全部文本内容
    with open(str(full_path), "r") as f:
        content = f.read()
        
    # 返回包含绝对路径和文件内容的字典结构，供代理（Agent）使用
    return {
        "file_path": str(full_path),
        "content": content
    }

def list_files_tool(path: str) -> Dict[str, Any]:
    """
    列出用户指定目录中的文件和文件夹。
    :param path: 要列出文件的目录路径。
    :return: 包含目录路径及其下所有文件/文件夹列表的字典。
    """
    # 将传入的路径解析为标准的绝对路径对象
    full_path = resolve_abs_path(path)
    
    # 初始化一个空列表，用于存储目录下的所有文件和文件夹信息
    all_files = []
    
    # 遍历绝对路径下的所有项（文件或子目录）
    for item in full_path.iterdir():
        # 将每个项的名称和类型（文件为 "file"，目录为 "dir"）存入字典，并追加到列表中
        all_files.append({
            "filename": item.name,
            "type": "file" if item.is_file() else "dir"
        })
        
    # 返回包含绝对路径和文件列表的字典结构，供代理（Agent）使用
    return {
        "path": str(full_path),
        "files": all_files
    }

def edit_file_tool(path: str, old_str: str, new_str: str) -> Dict[str, Any]:
    """
    替换文件中第一次出现的 old_str 为 new_str。如果 old_str 为空，则用 new_str 创建或覆盖文件。
    :param path: 要编辑的文件的路径。
    :param old_str: 要被替换的目标字符串。
    :param new_str: 替换后的新字符串。
    :return: 一个包含文件路径和执行操作的字典。
    """
    # 解析并获取规范的绝对路径
    full_path = resolve_abs_path(path)
    p = Path(full_path)
    
    # 如果 old_str 为空，直接创建或覆盖文件内容
    if old_str == "":
        p.write_text(new_str, encoding="utf-8")
        return {
            "path": str(full_path),
            "action": "created_file"
        }
        
    # 读取文件的原始内容
    original = p.read_text(encoding="utf-8")
    
    # 检查文件中是否存在目标字符串
    if original.find(old_str) == -1:
        return {
            "path": str(full_path),
            "action": "old_str not found"
        }
        
    # 仅替换第一次出现的目标字符串
    edited = original.replace(old_str, new_str, 1)
    
    # 将修改后的内容写回文件
    p.write_text(edited, encoding="utf-8")
    return {
        "path": str(full_path),
        "action": "edited"
    }

TOOL_REGISTRY = {
    "read_file": read_file_tool,
    "list_files": list_files_tool,
    "edit_file": edit_file_tool
}

def get_tool_str_representation(tool_name: str) -> str:
    """
    获取指定工具的字符串表示形式，包含工具名称、文档说明及函数签名。
    :param tool_name: 工具名称（键）
    :return: 包含工具名称、描述和签名的格式化字符串
    """
    # 从工具注册表中根据名称获取对应的工具函数
    tool = TOOL_REGISTRY[tool_name]
    return f"""
    Name: {tool_name}
    Description: {tool.__doc__}
    Signature: {inspect.signature(tool)}
    """

def create_full_system_prompt() -> str:
    """
    组装并返回完整的系统提示词（System Prompt），
    将所有注册的工具名称、描述和签名拼接到基础模板中。
    :return: 包含所有工具详情的完整系统提示词字符串。
    """
    # 初始化一个空字符串，用于累加所有工具的字符串表示
    tool_str_repr = ""
    
    # 遍历工具注册表中的每一个工具名称
    for tool_name in TOOL_REGISTRY:
        # 拼接工具的标识头以及通过 get_tool_str_representation 获取的工具详细信息
        tool_str_repr += "TOOL\n===" + get_tool_str_representation(tool_name)
        # 在每个工具信息之间添加分隔线，使格式更清晰
        tool_str_repr += f"\n{"="*15}\n"
        
    # 将组装好的所有工具描述字符串填入 SYSTEM_PROMPT 的占位符中并返回
    return SYSTEM_PROMPT.format(tool_list_str=tool_str_repr)


def extract_tool_invocations(text: str) -> List[Tuple[str, Dict[str, Any]]]:
    """
    从文本中提取请求的工具调用列表，格式为 'tool: name({...})'。
    
    解析器期望在括号内使用单行且紧凑的 JSON 格式。
    
    :param text: 包含大模型回复内容的字符串。
    :return: 一个由 (工具名称, 参数字典) 组成的列表。
    """
    # 初始化一个空列表，用于存储解析出的工具调用及其参数
    invocations: List[Tuple[str, Dict[str, Any]]] = []
    
    # 逐行遍历输入文本
    for raw_line in text.splitlines():
        line = raw_line.strip()
        # 如果当前行不是以 "tool:" 开头，则跳过
        if not line.startswith("tool:"):
            continue
        
        # 期望的格式为: tool: NAME(JSON)
        try:
            # 截取 "tool:" 后面的内容并去除前后空白
            after = line[len("tool:") :].strip()
            # 以第一个左括号 "(" 将其分割为工具名称和参数部分
            name, rest = after.split("(", 1)
            name = name.strip()
            # 使用 JSON 解码器解析括号内的紧凑 JSON 参数
            args, _ = json.JSONDecoder().raw_decode(rest)
            # 将解析出的工具名称和参数字典添加到结果列表中
            invocations.append((name, args))
        except Exception:
            # 忽略格式错误的工具请求，防止程序崩溃
            continue
            
    return invocations


def execute_llm_call(conversation: List[Dict[str, str]]) -> str:
    """
    向 OpenAI 客户端发送对话历史请求，并获取大语言模型的回复文本。
    
    :param conversation: 包含对话历史的字典列表（每一项代表一条消息，包含 role 和 content）。
    :return: 大语言模型返回的文本响应内容。
    """
    response = openai_client.responses.create(
        model="gpt-5.6-terra",
        input=conversation,
        max_output_tokens=5000,
    )
    return response.output_text


def run_coding_agent_loop():
    """
    运行编码代理的主循环。
    初始化对话历史，接收用户输入，交由大语言模型处理，并根据大模型的响应
    自动解析并执行相应的工具调用，随后将工具执行结果反馈给模型，直至任务完成。
    """
    # 初始化对话历史，设置系统角色的 Prompt
    conversation = [{
        "role": "developer",
        "content": create_full_system_prompt()
    }] 
    while True:
        try:
            # 获取用户输入的任务或问题
            user_msg = input(f"{YOU_COLOR}You{RESET_COLOR}: ")
        except (EOFError, KeyboardInterrupt):
            # 捕获异常（如 Ctrl+C 或 EOF），安全退出循环
            break
            
        # 将用户的输入添加到对话历史中
        conversation.append({
            "role": "user",
            "content": user_msg.strip()
        })
        
        while True:
            # 调用大语言模型获取响应内容
            assistant_resp = execute_llm_call(conversation)
            
            # 解析大模型响应中包含的工具调用请求
            tool_invocations = extract_tool_invocations(assistant_resp)
            
            # 如果没有请求调用任何工具，说明是普通的文本回复，直接打印并记录到对话历史中，然后跳出内层循环等待下一次用户输入
            if not tool_invocations:
                print(f"{ASSISTANT_COLOR}Assistant{RESET_COLOR}: {assistant_resp}")
                conversation.append({
                    "role": "assistant",
                    "content": assistant_resp
                })
                break
                
            # 如果检测到工具调用，打印助手的响应并将其记录到对话历史
            print(f"{ASSISTANT_COLOR}Assistant{RESET_COLOR}: {assistant_resp}")
            conversation.append({
                "role": "assistant",
                "content": assistant_resp
            })
            
            # 遍历并依次执行模型请求的所有工具
            for name, args in tool_invocations:
                tool = TOOL_REGISTRY[name]
                resp = []
                # 根据不同的工具名称及其对应的参数执行相应的函数
                if name == "read_file":
                    resp = tool(args.get("filename", "."))
                elif name == "list_files":
                    resp = tool(args.get("path", "."))
                elif name == "edit_file":
                    resp = tool(args.get("path", "."), args.get("old_str", ""), args.get("new_str", ""))
                    
                # 将工具的执行结果格式化后作为用户信息追加到对话历史中，供大模型在下一轮迭代中参考
                conversation.append({
                    "role": "user",
                    "content": f"tool_result({json.dumps(resp)})"
                })

if __name__ == "__main__":
    run_coding_agent_loop()