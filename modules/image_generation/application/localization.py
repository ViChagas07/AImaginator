"""Catalogo backend de mensagens de recusa/aviso nos 11 idiomas suportados.

O idioma e o locale do SITE (header X-Locale), nunca o idioma detectado no
prompt. Nenhuma mensagem explica como contornar a moderacao.
"""

from __future__ import annotations

SUPPORTED_LOCALES: tuple[str, ...] = (
    "pt-BR",
    "en",
    "es",
    "fr",
    "de",
    "it",
    "ja",
    "zh",
    "ko",
    "ru",
    "ar",
)
DEFAULT_LOCALE = "pt-BR"

_LANGUAGE_ALIASES = {
    "pt": "pt-BR",
    "pt-br": "pt-BR",
    "en": "en",
    "es": "es",
    "fr": "fr",
    "de": "de",
    "it": "it",
    "ja": "ja",
    "zh": "zh",
    "ko": "ko",
    "ru": "ru",
    "ar": "ar",
}

_MESSAGES: dict[str, dict[str, str]] = {
    "pt-BR": {
        "content_blocked_nsfw": (
            "Não consigo criar esse tipo de conteúdo. Se quiser, descreva uma "
            "imagem com outro tema."
        ),
        "content_blocked_gore": (
            "Não consigo criar imagens com violência gráfica. Posso ajudar com "
            "outra ideia visual."
        ),
        "content_blocked_hate": (
            "Não consigo criar conteúdo de ódio ou que ataque pessoas. Vamos "
            "tentar outra ideia?"
        ),
        "content_blocked_self_harm": (
            "Não consigo criar esse tipo de conteúdo. Se você estiver passando "
            "por um momento difícil, procure uma pessoa de confiança ou um "
            "serviço de apoio."
        ),
        "out_of_scope": (
            "Sou especializado em criação e edição de imagens. Me diga qual "
            "imagem você gostaria de criar ou editar."
        ),
        "prompt_rejected": (
            "Não consegui interpretar esse pedido com segurança. Tente reformular "
            "a descrição da imagem."
        ),
        "assistant_unavailable": (
            "O assistente está indisponível no momento. Tente novamente em "
            "instantes."
        ),
        "temporarily_blocked": (
            "Você atingiu o limite de tentativas bloqueadas. Tente novamente mais "
            "tarde."
        ),
        "warning_level_1": (
            "Aviso: alguns pedidos recentes foram recusados pela política de "
            "conteúdo. Continue descrevendo apenas imagens permitidas."
        ),
        "account_under_review": (
            "Sua conta foi temporariamente limitada para revisão. Tente novamente "
            "mais tarde."
        ),
    },
    "en": {
        "content_blocked_nsfw": (
            "I can't create that kind of content. Try describing an image with a "
            "different theme."
        ),
        "content_blocked_gore": (
            "I can't create graphic violence imagery. I can help with another "
            "visual idea."
        ),
        "content_blocked_hate": (
            "I can't create hateful content or content that attacks people. "
            "Let's try another idea."
        ),
        "content_blocked_self_harm": (
            "I can't create that kind of content. If you're going through a "
            "difficult time, please reach out to someone you trust or a support "
            "service."
        ),
        "out_of_scope": (
            "I specialize in creating and editing images. Tell me what image you "
            "would like to create or edit."
        ),
        "prompt_rejected": (
            "I couldn't safely interpret that request. Try rephrasing the image "
            "description."
        ),
        "assistant_unavailable": (
            "The assistant is unavailable right now. Please try again shortly."
        ),
        "temporarily_blocked": (
            "You reached the limit of blocked attempts. Please try again later."
        ),
        "warning_level_1": (
            "Warning: some recent requests were refused by the content policy. "
            "Keep describing only allowed images."
        ),
        "account_under_review": (
            "Your account has been temporarily limited for review. Please try "
            "again later."
        ),
    },
    "es": {
        "content_blocked_nsfw": (
            "No puedo crear ese tipo de contenido. Describe una imagen con otro "
            "tema, por favor."
        ),
        "content_blocked_gore": (
            "No puedo crear imagenes con violencia explicita. Puedo ayudarte con "
            "otra idea visual."
        ),
        "content_blocked_hate": (
            "No puedo crear contenido de odio ni que ataque a personas. Probemos "
            "otra idea."
        ),
        "content_blocked_self_harm": (
            "No puedo crear ese tipo de contenido. Si estas pasando por un momento "
            "dificil, busca a una persona de confianza o un servicio de apoyo."
        ),
        "out_of_scope": (
            "Me especializo en crear y editar imagenes. Dime que imagen te "
            "gustaria crear o editar."
        ),
        "prompt_rejected": (
            "No pude interpretar esa solicitud de forma segura. Intenta reformular "
            "la descripcion de la imagen."
        ),
        "assistant_unavailable": (
            "El asistente no esta disponible en este momento. Intentalo de nuevo "
            "en unos instantes."
        ),
        "temporarily_blocked": (
            "Alcanzaste el limite de intentos bloqueados. Intentalo de nuevo mas "
            "tarde."
        ),
        "warning_level_1": (
            "Aviso: algunas solicitudes recientes fueron rechazadas por la politica "
            "de contenido. Sigue describiendo solo imagenes permitidas."
        ),
        "account_under_review": (
            "Tu cuenta fue limitada temporalmente para revision. Intentalo de nuevo "
            "mas tarde."
        ),
    },
    "fr": {
        "content_blocked_nsfw": (
            "Je ne peux pas creer ce type de contenu. Decris une image sur un autre "
            "theme, s'il te plait."
        ),
        "content_blocked_gore": (
            "Je ne peux pas creer d'images de violence graphique. Je peux t'aider "
            "avec une autre idee visuelle."
        ),
        "content_blocked_hate": (
            "Je ne peux pas creer de contenu haineux ni d'attaques envers des "
            "personnes. Essayons une autre idee."
        ),
        "content_blocked_self_harm": (
            "Je ne peux pas creer ce type de contenu. Si tu traverses un moment "
            "difficile, tourne-toi vers une personne de confiance ou un service "
            "d'aide."
        ),
        "out_of_scope": (
            "Je suis specialise dans la creation et la retouche d'images. Dis-moi "
            "quelle image tu souhaites creer ou modifier."
        ),
        "prompt_rejected": (
            "Je n'ai pas pu interpreter cette demande en toute securite. Essaie de "
            "reformuler la description de l'image."
        ),
        "assistant_unavailable": (
            "L'assistant est indisponible pour le moment. Reessaie dans un instant."
        ),
        "temporarily_blocked": (
            "Tu as atteint la limite de tentatives bloquees. Reessaie plus tard."
        ),
        "warning_level_1": (
            "Avertissement : certaines demandes recentes ont ete refusees par la "
            "politique de contenu. Continue a decrire uniquement des images "
            "autorisees."
        ),
        "account_under_review": (
            "Ton compte a ete temporairement limite pour verification. Reessaie "
            "plus tard."
        ),
    },
    "de": {
        "content_blocked_nsfw": (
            "Ich kann solche Inhalte nicht erstellen. Beschreibe bitte ein Bild "
            "mit einem anderen Thema."
        ),
        "content_blocked_gore": (
            "Ich kann keine explizite Gewalt darstellen. Ich helfe gern mit einer "
            "anderen Bildidee."
        ),
        "content_blocked_hate": (
            "Ich kann keine hasserfuellten Inhalte oder Angriffe auf Menschen "
            "erstellen. Versuchen wir eine andere Idee."
        ),
        "content_blocked_self_harm": (
            "Ich kann solche Inhalte nicht erstellen. Wenn du eine schwere Zeit "
            "durchmachst, wende dich bitte an eine vertraute Person oder einen "
            "Hilfsdienst."
        ),
        "out_of_scope": (
            "Ich bin auf das Erstellen und Bearbeiten von Bildern spezialisiert. "
            "Sag mir, welches Bild du erstellen oder bearbeiten moechtest."
        ),
        "prompt_rejected": (
            "Ich konnte diese Anfrage nicht sicher einordnen. Formuliere die "
            "Bildbeschreibung bitte neu."
        ),
        "assistant_unavailable": (
            "Der Assistent ist gerade nicht verfuegbar. Versuche es gleich noch "
            "einmal."
        ),
        "temporarily_blocked": (
            "Du hast das Limit blockierter Versuche erreicht. Versuche es spaeter "
            "erneut."
        ),
        "warning_level_1": (
            "Hinweis: Einige letzte Anfragen wurden durch die Inhaltsrichtlinie "
            "abgelehnt. Beschreibe weiterhin nur erlaubte Bilder."
        ),
        "account_under_review": (
            "Dein Konto wurde voruebergehend zur Pruefung eingeschraenkt. Versuche "
            "es spaeter erneut."
        ),
    },
    "it": {
        "content_blocked_nsfw": (
            "Non posso creare questo tipo di contenuto. Descrivi un'immagine con "
            "un altro tema."
        ),
        "content_blocked_gore": (
            "Non posso creare immagini con violenza esplicita. Posso aiutarti con "
            "un'altra idea visiva."
        ),
        "content_blocked_hate": (
            "Non posso creare contenuti d'odio o che attacchino persone. Proviamo "
            "un'altra idea."
        ),
        "content_blocked_self_harm": (
            "Non posso creare questo tipo di contenuto. Se stai attraversando un "
            "momento difficile, rivolgiti a una persona di fiducia o a un servizio "
            "di supporto."
        ),
        "out_of_scope": (
            "Sono specializzato nella creazione e modifica di immagini. Dimmi quale "
            "immagine vorresti creare o modificare."
        ),
        "prompt_rejected": (
            "Non sono riuscito a interpretare questa richiesta in modo sicuro. "
            "Prova a riformulare la descrizione dell'immagine."
        ),
        "assistant_unavailable": (
            "L'assistente non e disponibile in questo momento. Riprova tra poco."
        ),
        "temporarily_blocked": (
            "Hai raggiunto il limite di tentativi bloccati. Riprova piu tardi."
        ),
        "warning_level_1": (
            "Avviso: alcune richieste recenti sono state rifiutate dalla politica "
            "sui contenuti. Continua a descrivere solo immagini consentite."
        ),
        "account_under_review": (
            "Il tuo account e stato temporaneamente limitato per la revisione. "
            "Riprova piu tardi."
        ),
    },
    "ja": {
        "content_blocked_nsfw": (
            "その種類のコンテンツは作成できません。別のテーマの画像を説明してください。"
        ),
        "content_blocked_gore": (
            "過激な暴力の画像は作成できません。別のビジュアルアイデアならお手伝いできます。"
        ),
        "content_blocked_hate": (
            "憎悪や人を攻撃するコンテンツは作成できません。別のアイデアを試しましょう。"
        ),
        "content_blocked_self_harm": (
            "その種類のコンテンツは作成できません。つらい気持ちのときは、信頼できる人や"
            "支援サービスに相談してください。"
        ),
        "out_of_scope": (
            "画像の作成と編集を専門にしています。作成または編集したい画像を教えてください。"
        ),
        "prompt_rejected": (
            "このリクエストを安全に解釈できませんでした。画像の説明を言い換えてください。"
        ),
        "assistant_unavailable": (
            "アシスタントは現在利用できません。しばらくしてからもう一度お試しください。"
        ),
        "temporarily_blocked": (
            "ブロックされた試行の上限に達しました。しばらくしてからもう一度お試しください。"
        ),
        "warning_level_1": (
            "警告: 最近のリクエストの一部がコンテンツポリシーにより拒否されました。"
            "許可された画像のみを説明してください。"
        ),
        "account_under_review": (
            "アカウントは確認のため一時的に制限されています。しばらくしてからもう一度"
            "お試しください。"
        ),
    },
    "zh": {
        "content_blocked_nsfw": "我无法创建此类内容。请描述其他主题的图像。",
        "content_blocked_gore": "我无法创建露骨暴力的图像。我可以帮你尝试其他视觉创意。",
        "content_blocked_hate": "我无法创建仇恨或攻击他人的内容。我们换一个想法吧。",
        "content_blocked_self_harm": (
            "我无法创建此类内容。如果你正经历困难时期，请向信任的人或支持服务寻求帮助。"
        ),
        "out_of_scope": "我专注于创建和编辑图像。请告诉我你想创建或编辑什么图像。",
        "prompt_rejected": "我无法安全地理解这个请求。请尝试重新描述图像。",
        "assistant_unavailable": "助手暂时不可用。请稍后再试。",
        "temporarily_blocked": "你已达到被阻止尝试的上限。请稍后再试。",
        "warning_level_1": "警告：最近的一些请求因内容政策被拒绝。请继续只描述允许的图像。",
        "account_under_review": "你的账户已被临时限制以进行审核。请稍后再试。",
    },
    "ko": {
        "content_blocked_nsfw": "그런 종류의 콘텐츠는 만들 수 없습니다. 다른 주제의 이미지를 설명해 주세요.",
        "content_blocked_gore": "노골적인 폭력 이미지는 만들 수 없습니다. 다른 시각적 아이디어를 도와드릴 수 있습니다.",
        "content_blocked_hate": "혐오나 사람을 공격하는 콘텐츠는 만들 수 없습니다. 다른 아이디어를 시도해 봅시다.",
        "content_blocked_self_harm": (
            "그런 종류의 콘텐츠는 만들 수 없습니다. 힘든 시간을 보내고 있다면 신뢰할 수 있는 "
            "사람이나 지원 서비스에 도움을 요청해 주세요."
        ),
        "out_of_scope": "저는 이미지 생성과 편집을 전문으로 합니다. 만들거나 편집하고 싶은 이미지를 알려 주세요.",
        "prompt_rejected": "이 요청을 안전하게 해석하지 못했습니다. 이미지 설명을 다시 작성해 주세요.",
        "assistant_unavailable": "어시스턴트를 지금 사용할 수 없습니다. 잠시 후 다시 시도해 주세요.",
        "temporarily_blocked": "차단된 시도 한도에 도달했습니다. 나중에 다시 시도해 주세요.",
        "warning_level_1": "경고: 최근 요청 일부가 콘텐츠 정책으로 거부되었습니다. 허용된 이미지만 설명해 주세요.",
        "account_under_review": "계정이 검토를 위해 일시적으로 제한되었습니다. 나중에 다시 시도해 주세요.",
    },
    "ru": {
        "content_blocked_nsfw": (
            "Я не могу создавать такой контент. Опишите изображение на другую тему."
        ),
        "content_blocked_gore": (
            "Я не могу создавать изображения с откровенным насилием. Могу помочь с "
            "другой визуальной идеей."
        ),
        "content_blocked_hate": (
            "Я не могу создавать враждебный контент или нападки на людей. "
            "Попробуем другую идею."
        ),
        "content_blocked_self_harm": (
            "Я не могу создавать такой контент. Если вам сейчас трудно, "
            "обратитесь к доверенному человеку или в службу поддержки."
        ),
        "out_of_scope": (
            "Я специализируюсь на создании и редактировании изображений. "
            "Опишите, какое изображение вы хотите создать или изменить."
        ),
        "prompt_rejected": (
            "Не удалось безопасно понять этот запрос. Попробуйте иначе описать "
            "изображение."
        ),
        "assistant_unavailable": (
            "Ассистент сейчас недоступен. Попробуйте еще раз через некоторое время."
        ),
        "temporarily_blocked": (
            "Вы достигли предела заблокированных попыток. Попробуйте позже."
        ),
        "warning_level_1": (
            "Предупреждение: некоторые недавние запросы были отклонены правилами "
            "контента. Описывайте только разрешенные изображения."
        ),
        "account_under_review": (
            "Ваш аккаунт временно ограничен для проверки. Попробуйте позже."
        ),
    },
    "ar": {
        "content_blocked_nsfw": "لا يمكنني إنشاء هذا النوع من المحتوى. صف صورة بموضوع آخر.",
        "content_blocked_gore": "لا يمكنني إنشاء صور عنف صريح. يمكنني المساعدة بفكرة بصرية أخرى.",
        "content_blocked_hate": "لا يمكنني إنشاء محتوى كراهية أو هجوم على الأشخاص. لنجرب فكرة أخرى.",
        "content_blocked_self_harm": (
            "لا يمكنني إنشاء هذا النوع من المحتوى. إذا كنت تمر بوقت صعب، فتواصل مع "
            "شخص تثق به أو خدمة دعم."
        ),
        "out_of_scope": "أنا متخصص في إنشاء الصور وتحريرها. أخبرني بالصورة التي تريد إنشاءها أو تعديلها.",
        "prompt_rejected": "لم أتمكن من فهم هذا الطلب بأمان. حاول إعادة صياغة وصف الصورة.",
        "assistant_unavailable": "المساعد غير متاح الآن. حاول مرة أخرى بعد قليل.",
        "temporarily_blocked": "لقد وصلت إلى حد المحاولات المحظورة. حاول مرة أخرى لاحقاً.",
        "warning_level_1": "تنبيه: تم رفض بعض الطلبات الأخيرة بسبب سياسة المحتوى. استمر في وصف الصور المسموح بها فقط.",
        "account_under_review": "تم تقييد حسابك مؤقتاً للمراجعة. حاول مرة أخرى لاحقاً.",
    },
}


_EXTRA_MESSAGES = {
    "pt-BR": "Dados inválidos. Revise os campos e tente novamente.",
    "en": "Invalid input. Check the fields and try again.",
    "es": "Datos no validos. Revisa los campos e intentalo de nuevo.",
    "fr": "Donnees invalides. Verifie les champs et reessaie.",
    "de": "Ungueltige Eingabe. Pruefe die Felder und versuche es erneut.",
    "it": "Dati non validi. Controlla i campi e riprova.",
    "ja": "???????????????????????????",
    "zh": "??????????????",
    "ko": "??? ???? ????. ??? ???? ?? ??? ???.",
    "ru": "???????????? ??????. ????????? ???? ? ?????????? ?????.",
    "ar": "?????? ??? ?????. ???? ?? ?????? ????? ??? ????.",
}
for _locale, _message in _EXTRA_MESSAGES.items():
    _MESSAGES[_locale]["invalid_input"] = _message


_IMAGE_MESSAGES = {
    "pt-BR": {
        "image_blocked_nsfw": "A imagem gerada foi bloqueada pela política de conteúdo.",
        "image_blocked_gore": "A imagem gerada foi bloqueada por conter violência gráfica.",
        "image_blocked_hate": "A imagem gerada foi bloqueada por conter ódio.",
        "image_blocked_self_harm": "A imagem gerada foi bloqueada por conter autolesão.",
        "source_image_blocked_nsfw": "A imagem enviada foi bloqueada pela política de conteúdo.",
        "source_image_blocked_gore": "A imagem enviada foi bloqueada por conter violência gráfica.",
        "source_image_blocked_hate": "A imagem enviada foi bloqueada por conter ódio.",
        "source_image_blocked_self_harm": "A imagem enviada foi bloqueada por conter autolesão.",
        "image_moderation_unavailable": "Não foi possível verificar a imagem agora. Tente novamente em instantes.",
        "upscale_limit_reached": "Você atingiu o limite diário de ampliações. Tente novamente mais tarde."
    },
    "en": {
        "image_blocked_nsfw": "The generated image was blocked by the content policy.",
        "image_blocked_gore": "The generated image was blocked because it contains graphic violence.",
        "image_blocked_hate": "The generated image was blocked because it contains hateful content.",
        "image_blocked_self_harm": "The generated image was blocked because it contains self-harm.",
        "source_image_blocked_nsfw": "The uploaded image was blocked by the content policy.",
        "source_image_blocked_gore": "The uploaded image was blocked because it contains graphic violence.",
        "source_image_blocked_hate": "The uploaded image was blocked because it contains hateful content.",
        "source_image_blocked_self_harm": "The uploaded image was blocked because it contains self-harm.",
        "image_moderation_unavailable": "We could not verify the image right now. Please try again shortly.",
        "upscale_limit_reached": "You reached the daily upscale limit. Please try again later."
    },
    "es": {
        "image_blocked_nsfw": "La imagen generada fue bloqueada por la política de contenido.",
        "image_blocked_gore": "La imagen generada fue bloqueada porque contiene violencia gráfica.",
        "image_blocked_hate": "La imagen generada fue bloqueada porque contiene contenido que incita al odio.",
        "image_blocked_self_harm": "La imagen generada fue bloqueada porque contiene autolesiones.",
        "source_image_blocked_nsfw": "La imagen cargada fue bloqueada por la política de contenido.",
        "source_image_blocked_gore": "La imagen cargada fue bloqueada porque contiene violencia gráfica.",
        "source_image_blocked_hate": "La imagen cargada fue bloqueada porque contiene contenido que incita al odio.",
        "source_image_blocked_self_harm": "La imagen cargada fue bloqueada porque contiene autolesiones.",
        "image_moderation_unavailable": "No pudimos verificar la imagen en este momento. Inténtelo de nuevo en breve.",
        "upscale_limit_reached": "Has alcanzado el límite de aumento diario. Inténtelo de nuevo más tarde."
    },
    "fr": {
        "image_blocked_nsfw": "L'image générée a été bloquée par la politique de contenu.",
        "image_blocked_gore": "L'image générée a été bloquée car elle contient de la violence graphique.",
        "image_blocked_hate": "L'image générée a été bloquée car elle contient du contenu haineux.",
        "image_blocked_self_harm": "L'image générée a été bloquée car elle contient de l'automutilation.",
        "source_image_blocked_nsfw": "L'image téléchargée a été bloquée par la politique de contenu.",
        "source_image_blocked_gore": "L'image téléchargée a été bloquée car elle contient de la violence graphique.",
        "source_image_blocked_hate": "L'image téléchargée a été bloquée car elle contient du contenu haineux.",
        "source_image_blocked_self_harm": "L'image téléchargée a été bloquée car elle contient des images d'automutilation.",
        "image_moderation_unavailable": "Nous n'avons pas pu vérifier l'image pour le moment. Veuillez réessayer sous peu.",
        "upscale_limit_reached": "Vous avez atteint la limite de mise à niveau quotidienne. Veuillez réessayer plus tard."
    },
    "de": {
        "image_blocked_nsfw": "Das generierte Bild wurde durch die Inhaltsrichtlinie blockiert.",
        "image_blocked_gore": "Das generierte Bild wurde blockiert, da es drastische Gewaltdarstellungen enthält.",
        "image_blocked_hate": "Das generierte Bild wurde blockiert, da es hasserfüllte Inhalte enthält.",
        "image_blocked_self_harm": "Das generierte Bild wurde blockiert, da es Selbstverletzung enthält.",
        "source_image_blocked_nsfw": "Das hochgeladene Bild wurde durch die Inhaltsrichtlinie blockiert.",
        "source_image_blocked_gore": "Das hochgeladene Bild wurde blockiert, da es drastische Gewaltdarstellungen enthält.",
        "source_image_blocked_hate": "Das hochgeladene Bild wurde blockiert, da es hasserfüllte Inhalte enthält.",
        "source_image_blocked_self_harm": "Das hochgeladene Bild wurde blockiert, da es Selbstverletzung enthält.",
        "image_moderation_unavailable": "Wir konnten das Bild derzeit nicht überprüfen. Bitte versuchen Sie es in Kürze noch einmal.",
        "upscale_limit_reached": "Sie haben das tägliche Upscale-Limit erreicht. Bitte versuchen Sie es später noch einmal."
    },
    "it": {
        "image_blocked_nsfw": "L'immagine generata è stata bloccata dalla policy sui contenuti.",
        "image_blocked_gore": "L'immagine generata è stata bloccata perché contiene violenza grafica.",
        "image_blocked_hate": "L'immagine generata è stata bloccata perché contiene contenuti che incitano all'odio.",
        "image_blocked_self_harm": "L'immagine generata è stata bloccata perché contiene atti di autolesionismo.",
        "source_image_blocked_nsfw": "L'immagine caricata è stata bloccata dalla politica sui contenuti.",
        "source_image_blocked_gore": "L'immagine caricata è stata bloccata perché contiene violenza esplicita.",
        "source_image_blocked_hate": "L'immagine caricata è stata bloccata perché contiene contenuti che incitano all'odio.",
        "source_image_blocked_self_harm": "L'immagine caricata è stata bloccata perché contiene atti di autolesionismo.",
        "image_moderation_unavailable": "Non è stato possibile verificare l'immagine in questo momento. Per favore riprova a breve.",
        "upscale_limit_reached": "Hai raggiunto il limite massimo giornaliero. Per favore riprova più tardi."
    },
    "ja": {
        "image_blocked_nsfw": "生成された画像はコンテンツ ポリシーによってブロックされました。",
        "image_blocked_gore": "生成された画像は、暴力的な描写が含まれているためブロックされました。",
        "image_blocked_hate": "生成された画像は、嫌がらせ的なコンテンツが含まれているためブロックされました。",
        "image_blocked_self_harm": "生成された画像は自傷行為を含むためブロックされました。",
        "source_image_blocked_nsfw": "アップロードされた画像はコンテンツ ポリシーによってブロックされました。",
        "source_image_blocked_gore": "アップロードされた画像は、暴力的な描写が含まれているためブロックされました。",
        "source_image_blocked_hate": "アップロードされた画像は、嫌がらせ的なコンテンツが含まれているためブロックされました。",
        "source_image_blocked_self_harm": "アップロードされた画像は自傷行為を含むためブロックされました。",
        "image_moderation_unavailable": "現在画像を確認できませんでした。しばらくしてからもう一度お試しください。",
        "upscale_limit_reached": "1 日のアップスケール制限に達しました。後でもう一度試してください。"
    },
    "zh": {
        "image_blocked_nsfw": "生成的图像被内容策略阻止。",
        "image_blocked_gore": "生成的图像因包含暴力画面而被屏蔽。",
        "image_blocked_hate": "生成的图像因包含仇恨内容而被屏蔽。",
        "image_blocked_self_harm": "生成的图像因包含自残内容而被屏蔽。",
        "source_image_blocked_nsfw": "上传的图像被内容政策阻止。",
        "source_image_blocked_gore": "上传的图片因包含暴力画面而被屏蔽。",
        "source_image_blocked_hate": "上传的图片因包含仇恨内容而被屏蔽。",
        "source_image_blocked_self_harm": "上传的图片因包含自残内容而被屏蔽。",
        "image_moderation_unavailable": "我们现在无法验证该图像。请稍后重试。",
        "upscale_limit_reached": "您已达到每日高档限额。请稍后重试。"
    },
    "ko": {
        "image_blocked_nsfw": "생성된 이미지가 콘텐츠 정책에 의해 차단되었습니다.",
        "image_blocked_gore": "생성된 이미지는 노골적인 폭력을 포함하고 있기 때문에 차단되었습니다.",
        "image_blocked_hate": "생성된 이미지에는 증오성 콘텐츠가 포함되어 있어 차단되었습니다.",
        "image_blocked_self_harm": "생성된 이미지에는 자해 내용이 포함되어 있어 차단되었습니다.",
        "source_image_blocked_nsfw": "업로드된 이미지가 콘텐츠 정책에 의해 차단되었습니다.",
        "source_image_blocked_gore": "업로드된 이미지는 노골적인 폭력을 포함하고 있어 차단되었습니다.",
        "source_image_blocked_hate": "업로드된 이미지에 증오성 콘텐츠가 포함되어 있어 차단되었습니다.",
        "source_image_blocked_self_harm": "업로드된 이미지에는 자해 내용이 포함되어 있어 차단되었습니다.",
        "image_moderation_unavailable": "지금은 이미지를 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.",
        "upscale_limit_reached": "일일 최대 한도에 도달했습니다. 나중에 다시 시도해 주세요."
    },
    "ru": {
        "image_blocked_nsfw": "Сгенерированное изображение было заблокировано политикой контента.",
        "image_blocked_gore": "Сгенерированное изображение было заблокировано, поскольку оно содержит изображения насилия.",
        "image_blocked_hate": "Сгенерированное изображение было заблокировано, поскольку оно содержит контент, разжигающий ненависть.",
        "image_blocked_self_harm": "Сгенерированное изображение было заблокировано, поскольку оно содержит элементы членовредительства.",
        "source_image_blocked_nsfw": "Загруженное изображение заблокировано политикой в ​​отношении контента.",
        "source_image_blocked_gore": "Загруженное изображение было заблокировано, поскольку оно содержит изображения насилия.",
        "source_image_blocked_hate": "Загруженное изображение было заблокировано, поскольку оно содержит контент, разжигающий ненависть.",
        "source_image_blocked_self_harm": "Загруженное изображение было заблокировано, поскольку оно содержит элементы членовредительства.",
        "image_moderation_unavailable": "Нам не удалось проверить изображение прямо сейчас. Пожалуйста, повторите попытку в ближайшее время.",
        "upscale_limit_reached": "Вы достигли дневного лимита повышенного класса. Пожалуйста, повторите попытку позже."
    },
    "ar": {
        "image_blocked_nsfw": "تم حظر الصورة التي تم إنشاؤها بواسطة سياسة المحتوى.",
        "image_blocked_gore": "تم حظر الصورة التي تم إنشاؤها لأنها تحتوي على مشاهد عنف.",
        "image_blocked_hate": "تم حظر الصورة التي تم إنشاؤها لأنها تحتوي على محتوى يحض على الكراهية.",
        "image_blocked_self_harm": "تم حظر الصورة التي تم إنشاؤها لأنها تحتوي على إيذاء النفس.",
        "source_image_blocked_nsfw": "تم حظر الصورة التي تم تحميلها بواسطة سياسة المحتوى.",
        "source_image_blocked_gore": "تم حظر الصورة التي تم تحميلها لأنها تحتوي على مشاهد عنف.",
        "source_image_blocked_hate": "تم حظر الصورة التي تم تحميلها لأنها تحتوي على محتوى يحض على الكراهية.",
        "source_image_blocked_self_harm": "تم حظر الصورة التي تم تحميلها لأنها تحتوي على إيذاء النفس.",
        "image_moderation_unavailable": "لم نتمكن من التحقق من الصورة في الوقت الحالي. يرجى المحاولة مرة أخرى قريبا.",
        "upscale_limit_reached": "لقد وصلت إلى الحد الأقصى اليومي. يرجى المحاولة مرة أخرى في وقت لاحق."
    }
}

for _locale, _messages in _IMAGE_MESSAGES.items():
    _MESSAGES[_locale].update(_messages)


_FEATURE_MESSAGES = {
    "pt-BR": {
        "feature_disabled": "A geração de imagens está temporariamente indisponível.",
        "original_unavailable": "O original privado desta geração não está disponível. Regenere a imagem para refinar ou ampliar."
    },
    "en": {
        "feature_disabled": "Image generation is temporarily unavailable.",
        "original_unavailable": "The private original for this generation is unavailable. Regenerate the image to refine or upscale it."
    },
    "es": {
        "feature_disabled": "La generacion de imagenes no esta disponible por el momento.",
        "original_unavailable": "El original privado de esta generacion no esta disponible. Vuelve a generar la imagen para refinarla o ampliarla."
    },
    "fr": {
        "feature_disabled": "La generation d'images est temporairement indisponible.",
        "original_unavailable": "L'original prive de cette generation est indisponible. Regenerez l'image pour la retoucher ou l'agrandir."
    },
    "de": {
        "feature_disabled": "Die Bildgenerierung ist voruebergehend nicht verfuegbar.",
        "original_unavailable": "Das private Original dieser Generierung ist nicht verfuegbar. Erzeuge das Bild erneut, um es zu verfeinern oder zu vergroessern."
    },
    "it": {
        "feature_disabled": "La generazione di immagini e temporaneamente non disponibile.",
        "original_unavailable": "L'originale privato di questa generazione non e disponibile. Rigenera l'immagine per rifinirla o ingrandirla."
    },
    "ja": {
        "feature_disabled": "画像生成は一時的に利用できません。",
        "original_unavailable": "この生成の非公開オリジナルは利用できません。画像を再生成して調整または拡大してください。"
    },
    "zh": {
        "feature_disabled": "图像生成暂时不可用。",
        "original_unavailable": "此生成的私有原图不可用。请重新生成图像以进行精修或放大。"
    },
    "ko": {
        "feature_disabled": "이미지 생성이 일시적으로 제공되지 않습니다.",
        "original_unavailable": "이 생성의 비공개 원본을 사용할 수 없습니다. 이미지를 다시 생성해 다듬거나 확대하세요."
    },
    "ru": {
        "feature_disabled": "Создание изображений временно недоступно.",
        "original_unavailable": "Закрытый оригинал этого изображения недоступен. Создайте изображение заново для уточнения или увеличения."
    },
    "ar": {
        "feature_disabled": "إنشاء الصور غير متاح مؤقتاً.",
        "original_unavailable": "الأصل الخاص بهذا التوليد غير متاح. أعد إنشاء الصورة لتحسينها أو تكبيرها."
    }
}

for _locale, _messages in _FEATURE_MESSAGES.items():
    _MESSAGES[_locale].update(_messages)

_QUEUE_MESSAGES: dict[str, dict[str, str]] = {
    "pt-BR": {
        "queue_publish_failed": (
            "Não foi possível iniciar a geração agora. Seu crédito foi "
            "devolvido; tente novamente."
        ),
        "queue_lost": (
            "A geração anterior foi perdida na fila. Seu crédito foi devolvido; " "tente novamente."
        ),
    },
    "en": {
        "queue_publish_failed": (
            "We couldn't start the generation right now. Your credit was "
            "refunded; please try again."
        ),
        "queue_lost": (
            "The previous generation was lost in the queue. Your credit was "
            "refunded; please try again."
        ),
    },
    "es": {
        "queue_publish_failed": (
            "No pudimos iniciar la generacion ahora. Tu credito fue devuelto; "
            "intentalo de nuevo."
        ),
        "queue_lost": (
            "La generacion anterior se perdio en la cola. Tu credito fue "
            "devuelto; intentalo de nuevo."
        ),
    },
    "fr": {
        "queue_publish_failed": (
            "Impossible de demarrer la generation pour le moment. Votre credit "
            "a ete rembourse ; reessayez."
        ),
        "queue_lost": (
            "La generation precedente a ete perdue dans la file. Votre credit a "
            "ete rembourse ; reessayez."
        ),
    },
    "de": {
        "queue_publish_failed": (
            "Die Generierung konnte gerade nicht gestartet werden. Dein "
            "Guthaben wurde erstattet; bitte versuche es erneut."
        ),
        "queue_lost": (
            "Die vorherige Generierung ging in der Warteschlange verloren. Dein "
            "Guthaben wurde erstattet; bitte versuche es erneut."
        ),
    },
    "it": {
        "queue_publish_failed": (
            "Non e stato possibile avviare la generazione ora. Il credito e "
            "stato rimborsato; riprova."
        ),
        "queue_lost": (
            "La generazione precedente e andata persa in coda. Il credito e "
            "stato rimborsato; riprova."
        ),
    },
    "ja": {
        "queue_publish_failed": (
            "現在、生成を開始できませんでした。クレジットは返金されました。"
            "もう一度お試しください。"
        ),
        "queue_lost": (
            "前回の生成はキューで失われました。クレジットは返金されました。"
            "もう一度お試しください。"
        ),
    },
    "zh": {
        "queue_publish_failed": "现在无法启动生成。积分已退还，请重试。",
        "queue_lost": "之前的生成在队列中丢失。积分已退还，请重试。",
    },
    "ko": {
        "queue_publish_failed": (
            "지금은 생성을 시작할 수 없습니다. 크레딧이 환불되었습니다. " "다시 시도해 주세요."
        ),
        "queue_lost": (
            "이전 생성이 대기열에서 손실되었습니다. 크레딧이 환불되었습니다. " "다시 시도해 주세요."
        ),
    },
    "ru": {
        "queue_publish_failed": (
            "Не удалось запустить генерацию сейчас. Кредит возвращён; " "попробуйте ещё раз."
        ),
        "queue_lost": (
            "Предыдущая генерация потерялась в очереди. Кредит возвращён; " "попробуйте ещё раз."
        ),
    },
    "ar": {
        "queue_publish_failed": ("تعذر بدء الإنشاء الآن. تم استرداد رصيدك؛ حاول مرة أخرى."),
        "queue_lost": (
            "فقدت عملية الإنشاء السابقة في قائمة الانتظار. تم استرداد رصيدك؛ " "حاول مرة أخرى."
        ),
    },
}

for _locale, _messages in _QUEUE_MESSAGES.items():
    _MESSAGES[_locale].update(_messages)


_PLATFORM_MESSAGES: dict[str, dict[str, str]] = {
    "pt-BR": {
        "engine_offline": "O motor de imagem está offline no momento. Tente novamente em instantes.",
        "maintenance": "O AImaginator está em manutenção. Volte em breve.",
        "hardware_busy": "O hardware está ocupado ou quente demais. Aguarde alguns minutos.",
        "thermal_abort": "A geração foi interrompida por proteção térmica. Tente novamente mais tarde.",
        "resource_abort": "A geração foi interrompida por falta de memória. Tente novamente mais tarde.",
    },
    "en": {
        "engine_offline": "The image engine is offline right now. Please try again shortly.",
        "maintenance": "AImaginator is under maintenance. Please come back soon.",
        "hardware_busy": "The hardware is busy or too hot. Please wait a few minutes.",
        "thermal_abort": "Generation stopped for thermal protection. Please try again later.",
        "resource_abort": "Generation stopped due to low memory. Please try again later.",
    },
    "es": {
        "engine_offline": "El motor de imagenes esta desconectado. Intentalo de nuevo en breve.",
        "maintenance": "AImaginator esta en mantenimiento. Vuelve pronto.",
        "hardware_busy": "El hardware esta ocupado o demasiado caliente. Espera unos minutos.",
        "thermal_abort": "La generacion se detuvo por proteccion termica. Intentalo mas tarde.",
        "resource_abort": "La generacion se detuvo por falta de memoria. Intentalo mas tarde.",
    },
    "fr": {
        "engine_offline": "Le moteur d'images est hors ligne. Reessayez dans un instant.",
        "maintenance": "AImaginator est en maintenance. Revenez bientot.",
        "hardware_busy": "Le materiel est occupe ou trop chaud. Patientez quelques minutes.",
        "thermal_abort": "La generation a ete arretee pour protection thermique. Reessayez plus tard.",
        "resource_abort": "La generation a ete arretee faute de memoire. Reessayez plus tard.",
    },
    "de": {
        "engine_offline": "Die Bild-Engine ist derzeit offline. Bitte versuche es gleich erneut.",
        "maintenance": "AImaginator wird gewartet. Bitte komm bald wieder.",
        "hardware_busy": "Die Hardware ist besetzt oder zu heiss. Bitte warte einige Minuten.",
        "thermal_abort": "Die Generierung wurde aus Hitzeschutz gestoppt. Bitte spaeter erneut versuchen.",
        "resource_abort": "Die Generierung wurde wegen Speichermangel gestoppt. Bitte spaeter erneut versuchen.",
    },
    "it": {
        "engine_offline": "Il motore immagini e offline. Riprova tra poco.",
        "maintenance": "AImaginator e in manutenzione. Torna presto.",
        "hardware_busy": "L'hardware e occupato o troppo caldo. Attendi qualche minuto.",
        "thermal_abort": "La generazione e stata interrotta per protezione termica. Riprova piu tardi.",
        "resource_abort": "La generazione e stata interrotta per memoria insufficiente. Riprova piu tardi.",
    },
    "ja": {
        "engine_offline": "画像エンジンは現在オフラインです。しばらくしてから再試行してください。",
        "maintenance": "AImaginator はメンテナンス中です。後でもう一度お越しください。",
        "hardware_busy": "ハードウェアが使用中か高温です。数分お待ちください。",
        "thermal_abort": "熱保護のため生成を中止しました。後で再試行してください。",
        "resource_abort": "メモリ不足のため生成を中止しました。後で再試行してください。",
    },
    "zh": {
        "engine_offline": "图像引擎当前离线。请稍后重试。",
        "maintenance": "AImaginator 正在维护中。请稍后再来。",
        "hardware_busy": "硬件忙碌或过热。请等待几分钟。",
        "thermal_abort": "生成因热保护而停止。请稍后重试。",
        "resource_abort": "生成因内存不足而停止。请稍后重试。",
    },
    "ko": {
        "engine_offline": "이미지 엔진이 현재 오프라인입니다. 잠시 후 다시 시도해 주세요.",
        "maintenance": "AImaginator가 점검 중입니다. 잠시 후 다시 방문해 주세요.",
        "hardware_busy": "하드웨어가 사용 중이거나 너무 뜨겁습니다. 몇 분 기다려 주세요.",
        "thermal_abort": "열 보호로 생성이 중단되었습니다. 나중에 다시 시도해 주세요.",
        "resource_abort": "메모리 부족으로 생성이 중단되었습니다. 나중에 다시 시도해 주세요.",
    },
    "ru": {
        "engine_offline": "Движок изображений сейчас офлайн. Попробуйте чуть позже.",
        "maintenance": "AImaginator на обслуживании. Загляните позже.",
        "hardware_busy": "Оборудование занято или перегрето. Подождите несколько минут.",
        "thermal_abort": "Генерация остановлена из-за тепловой защиты. Попробуйте позже.",
        "resource_abort": "Генерация остановлена из-за нехватки памяти. Попробуйте позже.",
    },
    "ar": {
        "engine_offline": "محرك الصور غير متصل حاليا. حاول مرة أخرى بعد قليل.",
        "maintenance": "AImaginator قيد الصيانة. عد قريبا.",
        "hardware_busy": "الجهاز مشغول أو ساخن جدا. انتظر بضع دقائق.",
        "thermal_abort": "توقف الإنشاء للحماية الحرارية. حاول لاحقا.",
        "resource_abort": "توقف الإنشاء بسبب نقص الذاكرة. حاول لاحقا.",
    },
}

for _locale, _messages in _PLATFORM_MESSAGES.items():
    _MESSAGES[_locale].update(_messages)

_CANCEL_MESSAGES: dict[str, str] = {
    "pt-BR": "Geração cancelada.",
    "en": "Generation canceled.",
    "es": "Generación cancelada.",
    "fr": "Génération annulée.",
    "de": "Generierung abgebrochen.",
    "it": "Generazione annullata.",
    "ja": "生成をキャンセルしました。",
    "zh": "生成已取消。",
    "ko": "생성이 취소되었습니다.",
    "ru": "Генерация отменена.",
    "ar": "تم إلغاء الإنشاء.",
}
for _locale, _message in _CANCEL_MESSAGES.items():
    _MESSAGES[_locale]["canceled"] = _message

WARNING_LEVEL_MESSAGES = {
    1: "warning_level_1",
    2: "temporarily_blocked",
    3: "account_under_review",
}


def resolve_locale(*candidates: str | None) -> str:
    """Resolve o locale do site, com fallback para pt-BR."""
    for raw in candidates:
        if not raw:
            continue
        for part in raw.split(","):
            token = part.strip().split(";")[0].strip()
            if not token:
                continue
            lowered = token.lower().replace("_", "-")
            if token in SUPPORTED_LOCALES:
                return token
            if lowered in _LANGUAGE_ALIASES:
                return _LANGUAGE_ALIASES[lowered]
            base = lowered.split("-", 1)[0]
            if base in _LANGUAGE_ALIASES:
                return _LANGUAGE_ALIASES[base]
    return DEFAULT_LOCALE


def message_for(code: str, locale: str) -> str:
    resolved = resolve_locale(locale)
    catalog = _MESSAGES.get(resolved) or _MESSAGES[DEFAULT_LOCALE]
    return catalog.get(code) or _MESSAGES[DEFAULT_LOCALE].get(code) or code


def warning_message_for(level: int, locale: str) -> str | None:
    code = WARNING_LEVEL_MESSAGES.get(level)
    return message_for(code, locale) if code else None


def all_message_keys() -> frozenset[str]:
    return frozenset(_MESSAGES[DEFAULT_LOCALE])
