import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

"""
本地与远程模型调用的流程区别：
远程api：
messages → 直接post请求 → 服务端内部拼接模板+推理 → 返回answer

本地模型：
messages(结构化对话) 
→ apply_chat_template 拼接模型专属prompt文本 
→ tokenizer(text) 转token id 
→ model.generate() 推理 
→ 解码输出
"""

# 指定模型ID, 自动从 Hugging Face Hub 下载所需的模型文件和分词器配置
model_id = "Qwen/Qwen1.5-0.5B-Chat"

# 设置设备，优先使用GPU
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

# 加载分词器
tokenizer = AutoTokenizer.from_pretrained(model_id)

# 加载模型，并将其移动到指定设备
model = AutoModelForCausalLM.from_pretrained(model_id).to(device)

print("模型和分词器加载完成！")

# 准备对话输入
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "你好，请介绍你自己。"},
]

# 使用分词器的模板格式化输入
# 如果使用 OpenAI 的 api，没有这一步，服务端内部自动做模板拼接，你不用管模型底层 prompt 格式
# 但是本地模型，必须要，因为开源模型没有统一对话格式，不同模型有完全不同的 prompt 包装规则
#
# tokenize的作用：
# False：返回拼接好的原始文本字符串（后面再单独 tokenizer 编码）
# True：直接返回 input_ids 数字 token 列
#
# add_generation_prompt: 自动追加助手输出起始标记, 比如 Qwen 会自动末尾加上 <|im_start|>assistant\n，告诉模型：现在轮到 AI 生成回答了。如果不加，模型分不清该轮到谁说话，会乱输出、重复用户提问、生成空内容。
text = tokenizer.apply_chat_template(
    messages, tokenize=False, add_generation_prompt=True
)

# 编码输入文本
model_inputs = tokenizer([text], return_tensors="pt").to(device)

print("编码后的输入文本:")
print(model_inputs)

# >>>
# {'input_ids': tensor([[151644, 8948, 198, 2610, 525, 264,  10950, 17847, 13,151645, 198, 151644, 872, 198, 108386, 37945, 100157, 107828,1773, 151645, 198, 151644, 77091, 198]], device='cuda:0'), 'attention_mask': tensor([[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]],
#        device='cuda:0')}


# 使用模型生成回答
# max_new_tokens 控制了模型最多能生成多少个新的Token
generated_ids = model.generate(model_inputs.input_ids, max_new_tokens=512)

# 将生成的 Token ID 截取掉输入部分
# 这样我们只解码模型新生成的部分
generated_ids = [
    output_ids[len(input_ids) :]
    for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
]

# 解码生成的 Token ID
response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

print("\n模型的回答:")
print(response)

# 我叫通义千问，是由阿里云研发的预训练语言模型，可以回答问题、创作文字，还能表达观点、撰写代码。我主要的功能是在多个领域提
# 供帮助，包括但不限于:语言理解、文本生成、机器翻译、问答系统等。有什么我可以帮到你的吗？
