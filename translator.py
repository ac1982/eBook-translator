import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import tiktoken
import json
import argparse
from openai_handler import translate_content
import sys
import os
import concurrent

# 加载配置文件
with open("config.json", "r") as f:
    config = json.load(f)
# 使用"config.json"文件打开一个文件对象，并使用json.load()方法加载配置文件内容到config变量中

model_name = config["model"]
# 从配置文件中获取模型名称并存储到model_name变量中

if model_name == "gpt-4":
    MAX_TOKENS = 2400
    THRESHOLD = 2000
elif model_name == "gpt-3.5-turbo":
    MAX_TOKENS = 1200
    THRESHOLD = 500
else:
    print(f"未知模型: {model_name}")
    sys.exit(1)
# 根据模型名称设置MAX_TOKENS和THRESHOLD。如果模型名称不在已知的模型列表中，打印错误消息并退出程序。

ENCODING_NAME = "cl100k_base"
# 设置编码名称为"cl100k_base"

total_tokens = 0
# 初始化总令牌数为0

max_workers = config.get("max_workers", None)
# 从配置文件中获取最大工作线程数，如果配置文件中没有指定，则为None

if max_workers is None:
    max_workers = os.cpu_count()
# 如果最大工作线程数未指定，则将其设置为可用的CPU核心数(os.cpu_count()返回CPU核心数)


def num_tokens_from_string(string: str) -> int:
    """Returns the number of tokens in a text string."""
    # 函数声明，接受一个名为string的字符串参数，返回一个整数类型的值

    encoding = tiktoken.encoding_for_model(config["model"])
    # 根据配置文件中的模型名称获取编码器
    # 使用模型名称从`tiktoken`模块中获取相应的编码器

    num_tokens = len(encoding.encode(string))
    # 使用编码器对文本字符串进行编码，并计算编码后的令牌数量
    # 通过对编码后的字符串返回的列表进行长度计算得到令牌数量

    return num_tokens
    # 返回令牌数量作为函数的结果


# 使用递归的方法翻译超过MAX_TOKENS的内容
def translate_recursive(soup, level=1):
    # 检查 soup 是否为空
    if not soup:
        # 如果为空,返回空字符串和0
        return "", 0

    children = list(soup.children)  # 获取 soup 的子节点列表
    children_number = len(children)  # 计算子节点的数量
    if config["test"]:
        print(f"Level {level} 的子节点(Children)数量{children_number}")

    translated_content = ""  # 初始化翻译后的内容字符串
    cost_tokens = 0  # 初始化已用 tokens 数量
    buffer = ""  # 初始化缓冲区字符串
    buffer_tokens = 0  # 初始化缓冲区 tokens 数量

    # 避免错误导致的无限递归
    if level >= 7:
        print(f"递归层数超过{level}层，停止程序。")
        sys.exit(1)

    for i, child in enumerate(children):  # 遍历子节点
        child_html = str(child)  # 将子节点转换为 HTML 字符串
        child_html = child_html.strip()  # 去除前导和尾随空格

        if not child_html:  # 如果child_html为空字符串
            continue  # 跳过当前循环迭代

        child_tokens = num_tokens_from_string(child_html)  # 计算子节点的 tokens 数量
        # 继续处理子节点的令牌数量...
        if child_tokens < MAX_TOKENS:
            # 如果子节点的 token 数量大于 THRESHOLD，先清空缓冲区，然后直接处理 child_html
            if child_tokens >= THRESHOLD:
                if buffer:
                    if config["test"]:
                        print(
                            f"Level:{level} 第{i+1} 子节点 > THRESHOLD\nBuffer不为空，Buffer的Tokens：{buffer_tokens}\n翻译Buffer内容: \n{buffer}\n"
                        )
                    translated_buffer, buffer_cost_tokens = translate_content(buffer)
                    translated_content += translated_buffer
                    cost_tokens += buffer_cost_tokens
                    buffer = ""
                    buffer_tokens = 0

                if config["test"]:
                    print(
                        f"该Level:{level} 第{i+1} 子节点 Tokens：{child_tokens} < THRESHOLD 直接处理"
                    )
                translated_child, child_cost_tokens = translate_content(child_html)
                translated_content += translated_child
                cost_tokens += child_cost_tokens

            # 如果子节点的 tokens 数量小于 THRESHOLD
            else:
                # 将较小的子节点添加到缓冲区，并累加 buffer_tokens
                buffer += child_html
                buffer_tokens += child_tokens
                # 如果添加后缓冲区超过THRESHOLD，那么清空缓冲区
                if buffer_tokens >= THRESHOLD:
                    if config["test"]:
                        print(
                            f"该Level:{level} 第{i+1} 子节点,把其添加到的Buffer后，Tokens超过Threshold。\nTokens：{buffer_tokens} \n翻译Buffer内容: \n{buffer}\n"
                        )
                    translated_buffer, buffer_cost_tokens = translate_content(buffer)
                    translated_content += translated_buffer
                    cost_tokens += buffer_cost_tokens
                    buffer = ""
                    buffer_tokens = 0
        else:
            # 先清空缓冲区
            if buffer:
                if config["test"]:
                    print(
                        f"该Level:{level} 第{i+1} 子节点Tokens：{buffer_tokens} > MAX_TOKENS \n清空Buffer后递归处理,Buffer: \n{buffer}\n"
                    )
                translated_buffer, buffer_cost_tokens = translate_content(buffer)
                translated_content += translated_buffer
                cost_tokens += buffer_cost_tokens
                buffer = ""
                buffer_tokens = 0

            # 递归处理子节点
            translated_child, child_cost_tokens = translate_recursive(child, level + 1)
            translated_content += translated_child
            cost_tokens += child_cost_tokens

    # 遍历结束，处理剩余的Buffer，如果不只是空字符
    if buffer.strip():
        if config["test"]:
            print(
                f"遍历Level:{level}结束，缓冲区仍有Buffer\nBuffer Tokens：{buffer_tokens} \n翻译Buffer:\n{buffer}\n"
            )
        translated_buffer, buffer_cost_tokens = translate_content(buffer)
        translated_content += translated_buffer
        cost_tokens += buffer_cost_tokens

    return translated_content, cost_tokens  # 返回翻译后的内容和已用 tokens 数量


# item 是 ebooklib book.get_items()的子内容，通常是html字符串
def translate_item(content):
    # global total_tokens  # 使用全局变量 total_tokens 来跟踪已翻译的 tokens 数量
    count = num_tokens_from_string(content)  # 计算输入内容的 tokens 数量
    item_cost_tokens = 0
    if config["test"]:
        print(f"该 ITEM 的tokens合计：{count}")

    if count < MAX_TOKENS:
        # 如果输入内容的 tokens 数量小于 MAX_TOKENS
        if config["test"]:
            print("Translating the entire content.\n")
        new_item_content, cost_tokens = translate_content(content)  # 直接翻译整个内容
        item_cost_tokens += cost_tokens  # 累加已用 tokens 数量
    else:
        # 如果输入内容的 tokens 数量大于 MAX_TOKENS，需要逐部分翻译
        if config["test"]:
            print("Translating the content by parts.\n")
        # 使用 BeautifulSoup 解析 HTML 内容
        soup = BeautifulSoup(content, "html.parser")
        translated_body, cost_tokens = translate_recursive(soup.body)  # 递归地翻译子元素
        item_cost_tokens += cost_tokens  # 累加已用 tokens 数量
        # 将翻译后的 body 内容替换原始 soup 对象中的 body 内容
        soup.body.clear()  # 清空原始 soup 对象中的 body 内容
        # 将翻译后的内容添加到 soup 的 body 中
        soup.body.append(BeautifulSoup(translated_body, "html.parser"))
        new_item_content = str(soup)  # 获取整个 HTML 字符串（包括翻译后的内容）

    return new_item_content, item_cost_tokens  # 返回翻译后的内容


if __name__ == "__main__":
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    # 创建一个线程池执行器，用于并行执行任务

    parser = argparse.ArgumentParser(description="Translate an EPUB file.")
    # 创建一个参数解析器，用于解析命令行参数
    parser.add_argument("input_file", type=str, help="The path to the input EPUB file.")
    # 添加一个位置参数，表示输入的EPUB文件的路径

    args = parser.parse_args()
    # 解析命令行参数并存储到args变量中

    try:
        book = epub.read_epub(args.input_file)
    except FileNotFoundError:
        print(f"文件 '{args.input_file}' 不存在，请检查文件名和路径是否正确。")
        sys.exit(1)
    # 尝试读取输入的EPUB文件，并将其存储到book变量中
    # 如果文件不存在，则打印错误消息并退出程序

    new_book = epub.EpubBook()
    # 创建一个新的EpubBook对象，用于存储翻译后的电子书

    dc_keys = [
        "identifier",
        "title",
        "language",
        "creator",
        "contributor",
        "publisher",
        "rights",
        "coverage",
        "date",
        "description",
    ]
    # 定义一个包含Dublin Core元数据关键字的列表

    for key in dc_keys:
        metadata = book.get_metadata("DC", key)
        # 获取原始电子书中特定关键字的Dublin Core元数据
        for entry in metadata:
            new_book.add_metadata("DC", key, entry[0], others=entry[1])
        # 将Dublin Core元数据添加到新的电子书中

    custom_metadata = book.get_metadata("OPF", None)
    # 获取原始电子书中的自定义元数据
    for entry in custom_metadata:
        if "name" in entry[1] and "content" in entry[1]:
            new_book.add_metadata(
                "OPF", entry[1]["name"], entry[1]["content"], others=entry[1]
            )
        # 将自定义元数据添加到新的电子书中

    item_count = 0  # 初始化项目计数为0
    items = list(book.get_items())  # 获取原始电子书中的所有项目，并将其转换为列表
    total_items = len(items)  # 获取项目的总数

    item_results = {}  # 创建一个空的字典，用于存储处理结果
    item_futures = []  # 创建一个空列表，用于存储任务的未来对象
    total_tokens = 0  # 记录总的令牌数量

    for index, item in enumerate(items):
        if item.get_type() == ebooklib.ITEM_DOCUMENT:  # 检查项目类型是否为文档
            item_count += 1  # 项目计数加1
            if config["test"] and item_count > max(1, total_items // 10):
                break  # 如果项目数量超过指定阈值，则跳出循环

            original_content = item.get_content().decode("utf-8")  # 获取原始内容并解码为UTF-8格式
            future = executor.submit(
                translate_item, original_content
            )  # 提交翻译任务给执行器，获得一个未来对象
            item_futures.append((index, item, future))  # 将索引、项目和未来对象添加到列表中

    for index, item, future in item_futures:
        new_content, item_cost_tokens = future.result()  # 获取未来对象的结果（阻塞，直到结果可用）
        total_tokens += item_cost_tokens  # 增加令牌数量
        item_results[index] = (new_content, item_cost_tokens)  # 将处理结果存储到字典中

    new_book.toc = book.toc  # 将原始电子书的目录复制到新的电子书中
    new_book.spine = book.spine  # 将原始电子书的内容顺序复制到新的电子书中
    new_book.guide = book.guide  # 将原始电子书的引导信息复制到新的电子书中

    for index, item in enumerate(items):
        if index in item_results:  # 检查处理结果中是否存在当前索引
            new_content, _ = item_results[index]  # 获取处理结果中的新内容
            new_item = epub.EpubItem(
                uid=item.id,
                file_name=item.file_name,
                media_type=item.media_type,
                content=new_content,
            )  # 创建一个新的EpubItem对象
            new_book.add_item(new_item)  # 将新的项目添加到新的电子书中
            # 更新目录
            for toc_entry in new_book.toc:
                if toc_entry.href == item.file_name:
                    toc_entry.item = new_item  # 更新目录中的项目引用
        else:
            new_book.add_item(item)  # 如果处理结果中不存在当前索引，则将原始项目添加到新的电子书中

    output_file = args.input_file.split(".")[0] + "_zh.epub"  # 根据输入文件名生成输出文件名
    # 使用.split('.')获取文件名部分（不含扩展名），然后添加'_zh.epub'后缀
    epub.write_epub(output_file, new_book)  # 将新的电子书
