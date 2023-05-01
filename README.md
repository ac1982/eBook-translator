# Ebook-Translator: 
![eBook-GPT-Translator Logo](./logo.png)
Ebook-Translator 是一个基于人工智能提示的原生工程项目。换句话说，这个项目绝大部分是由我提问，而GPT负责执开发的。

## 特点

- 保留电子书的原始格式，包括图片、摘要、引用、斜体、粗体、链接等
- 原生的基于人工智能提示的工程，您可以修改提示和温度来调整翻译结果，符合自己的信达雅标准

## 开发原因
- 现有的翻译方案无法保留原始格式
- 通过与 GPT 合作，探索 GPT 和自己的边界

## 使用方法
```bash
git clone 
pip install -r requrements.txt
mv config_example.json config.json
```
把你自己的OpenAI-API-Key，通常是```sk-```开头的一串字符，填写到```config.json```里面的```openai_api_key```。

```bash
python3 translator.py your_ebook.epub
```
