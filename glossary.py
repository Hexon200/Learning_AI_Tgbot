# Technical glossary for quiz bot

GLOSSARY = {
    "transformer": {
        "keywords": ["transformer", "transformers", "трансформер", "трансформеры", "трансформеров"],
        "en": "Transformer: A neural network architecture based on self-attention mechanisms, widely used for processing sequential data like text.",
        "ru": "Трансформер: Архитектура нейросетей, основанная на механизме самовнимания, широко используемая для обработки последовательностей текста."
    },
    "self-attention": {
        "keywords": ["self-attention", "attention", "самовнимание", "внимание", "внимания"],
        "en": "Self-Attention: A mechanism that calculates how much focus a token should place on other tokens in a sequence to capture context.",
        "ru": "Самовнимание: Механизм, вычисляющий степень связи каждого токена с остальными токенами в последовательности для понимания контекста."
    },
    "llm": {
        "keywords": ["llm", "llms", "large language model", "языковая модель", "языковые модели"],
        "en": "LLM (Large Language Model): A deep learning model trained on massive text datasets to understand, generate, and process human language.",
        "ru": "LLM (Большая языковая модель): Модель глубокого обучения, обученная на огромных объемах текста для понимания и генерации человеческого языка."
    },
    "pretraining": {
        "keywords": ["pretraining", "pre-training", "pretrained", "pre-trained", "предобучение", "предобученная", "предобученной"],
        "en": "Pre-training: The initial phase of training a model on unlabelled text to learn general grammar, facts, and language structure.",
        "ru": "Предобучение: Начальный этап обучения модели на неразмеченном тексте для усвоения грамматики, фактов и структуры языка."
    },
    "fine-tuning": {
        "keywords": ["fine-tuning", "finetuning", "fine-tuned", "дообучение", "дообученной", "настройки"],
        "en": "Fine-tuning: The process of training a pre-trained model on a smaller, specific dataset to adapt it to a particular task or behavior.",
        "ru": "Дообучение (Fine-tuning): Процесс настройки предобученной модели на узком наборе данных для конкретной задачи."
    },
    "token": {
        "keywords": ["token", "tokens", "tokenization", "токен", "токены", "токенов", "токенизация"],
        "en": "Token: A basic unit of text processed by an LLM, which can be a single character, subword, or whole word.",
        "ru": "Токен: Базовая единица текста, обрабатываемая моделью (символ, часть слова или целое слово)."
    },
    "embedding": {
        "keywords": ["embedding", "embeddings", "векторное представление", "векторные представления", "эмбеддинг", "эмбеддинги"],
        "en": "Embedding: A vector of numbers representing a token, capturing its semantic meaning and similarity to other concepts.",
        "ru": "Эмбеддинг (Векторное представление): Вектор чисел, кодирующий смысловое значение токена для поиска совпадений."
    },
    "context window": {
        "keywords": ["context window", "context length", "контекстное окно", "окно контекста", "длина контекста"],
        "en": "Context Window: The maximum number of tokens a model can process in a single forward pass (memory limit of a prompt).",
        "ru": "Контекстное окно: Максимальное количество токенов, которое модель может обработать за раз (лимит памяти промпта)."
    },
    "logits": {
        "keywords": ["logits", "logit", "логиты", "логит"],
        "en": "Logits: The raw, unnormalized scoring output by the final layer of a neural network before applying softmax.",
        "ru": "Логиты: Сырые, ненормированные оценки, выдаваемые последним слоем нейросети перед применением softmax."
    },
    "softmax": {
        "keywords": ["softmax", "софтмакс"],
        "en": "Softmax: A function that turns raw output scores (logits) into a probability distribution that sums to 1.0.",
        "ru": "Softmax: Функция, преобразующая сырые оценки (логиты) в распределение вероятностей, сумма которых равна 1.0."
    },
    "kv cache": {
        "keywords": ["kv cache", "kv-cache", "кэш kv", "кэш ключей", "kv кэш", "кэширование kv", "кэша kv"],
        "en": "KV Cache: A technique that stores Key and Value vectors of past tokens during LLM generation to avoid recalculating them, speeding up inference.",
        "ru": "Кэш KV: Технология, сохраняющая векторы Key and Value для прошлых токенов во время генерации, чтобы избежать их пересчета и ускорить работу модели."
    },
    "gradient descent": {
        "keywords": ["gradient descent", "градиентный спуск", "градиентного спуска", "градиентному спуску"],
        "en": "Gradient Descent: An optimization algorithm used to minimize a model's error (loss) by iteratively updating weights in the opposite direction of the gradient.",
        "ru": "Градиентный спуск: Алгоритм оптимизации, используемый для минимизации ошибки (потерь) модели путем итеративного обновления весов в направлении, противоположном градиенту."
    },
    "backpropagation": {
        "keywords": ["backpropagation", "обратное распространение", "обратного распространения", "обратном распространении"],
        "en": "Backpropagation: A method to calculate gradients of the loss function with respect to neural network weights, using the calculus chain rule to enable learning.",
        "ru": "Обратное распространение (Backpropagation): Метод расчета градиентов функции потерь относительно весов нейросети с использованием цепного правила дифференцирования."
    },
    "activation function": {
        "keywords": ["activation function", "activation functions", "функция активации", "функции активации", "функций активации", "relu", "sigmoid", "сигмоид"],
        "en": "Activation Function: A mathematical formula (e.g. ReLU, Sigmoid) applied to a neuron's output to introduce non-linearity, allowing learning of complex patterns.",
        "ru": "Функция активации: Математическая формула (например, ReLU, Sigmoid), применяемая к выходу нейрона для введения нелинейности, позволяющая модели решать сложные задачи."
    },
    "reranking": {
        "keywords": ["reranking", "reranker", "реранжирование", "реранжирования", "реранкер", "реранкеры"],
        "en": "Reranking: A post-retrieval step in RAG where a secondary model (cross-encoder) re-scores retrieved document chunks to sort the most relevant ones to the top.",
        "ru": "Реранжирование: Этап после поиска в RAG, где дополнительная модель (кросс-кодировщик) переоценивает найденные фрагменты документов, чтобы отсортировать наиболее важные наверх."
    },
    "agentic rag": {
        "keywords": ["agentic rag", "агентный rag", "агентного rag"],
        "en": "Agentic RAG: An advanced RAG architecture where an LLM agent uses reasoning steps (like planning and self-correction) to query databases and evaluate retrieved facts.",
        "ru": "Агентный RAG: Продвинутая архитектура RAG, в которой LLM-агент использует шаги рассуждения (планирование, самопроверка), чтобы самостоятельно искать информацию и оценивать её."
    },
    "rlhf": {
        "keywords": ["rlhf", "human feedback", "отзывов людей", "обратной связи людей", "человеческим фидбеком"],
        "en": "RLHF (Reinforcement Learning from Human Feedback): A training method that aligns LLM outputs with human preferences (helpfulness, safety) using a reward model.",
        "ru": "RLHF: Обучение с подкреплением на основе отзывов людей — метод настройки ответов LLM в соответствии с человеческими предпочтениями (полезность, безопасность)."
    },
    "temperature": {
        "keywords": ["temperature", "температура", "температуры", "температурой"],
        "en": "Temperature: A parameter controlling randomness in LLM generation. Lower values make responses deterministic and precise; higher values increase creativity.",
        "ru": "Температура: Параметр генерации LLM, управляющий случайностью ответов. Низкие значения делают ответы точными и логичными, высокие — креативными и разнообразными."
    },
    "hallucination": {
        "keywords": ["hallucination", "hallucinations", "галлюцинация", "галлюцинации", "галлюцинаций", "галлюцинирует"],
        "en": "Hallucination: A phenomenon where an LLM confidently generates grammatically correct but factually incorrect, fabricated, or nonsensical information.",
        "ru": "Галлюцинация: Явление, при котором модель уверенно генерирует грамматически правильный, но фактически неверный, вымышленный или бессмысленный ответ."
    }
}


def detect_glossary_terms(text: str) -> list[str]:
    """Scans text for glossary keywords and returns list of term keys found."""
    if not text:
        return []
    text_lower = text.lower()
    found = []
    for term_key, info in GLOSSARY.items():
        for keyword in info["keywords"]:
            # Check for keyword match with word boundaries or simple substring
            if keyword in text_lower:
                found.append(term_key)
                break
    return found


def format_definitions(term_keys: list[str], lang: str = "en") -> str:
    """Formats definitions of requested terms in the specified language."""
    lines = []
    for key in term_keys:
        if key in GLOSSARY:
            lines.append(GLOSSARY[key].get(lang) or GLOSSARY[key].get("en"))
    return "\n\n".join(lines)
