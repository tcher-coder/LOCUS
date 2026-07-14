# Telegram Bot API — Rich Messages (официальная документация)

Дословная выгрузка раздела **Rich messages** со страницы
<https://core.telegram.org/bots/api#rich-messages> — методы, типы, синтаксис
разметки и лимиты. Скачано **2026-07-14**; все ссылки ведут на первоисточник.

Самодостаточный справочник: всё, что нужно знать, чтобы внедрить rich-сообщения
в бота с нуля — методы, типы, разметка, лимиты. Никаких допущений о конкретном
проекте или языке не делается.

**Важно про версии.** Механизм rich-сообщений — `sendRichMessage`,
`InputRichMessage` с полями `markdown`/`html`, а также сами блоки коллажа и
слайд-шоу (`RichBlockCollage`, `RichBlockSlideshow`) — появился в **Bot API 10.1**
(11 июня 2026). То есть теги `<tg-collage>` и `<tg-slideshow>` с картинками
**по HTTP-URL** работают с 10.1.

**Bot API 10.2** (14 июля 2026) добавил работу с собственными файлами:
`InputRichMessageMedia` и поле `media` у `InputRichMessage` — они позволяют
подставлять в разметку ссылки `tg://photo?id=…` и **загружать собственные файлы**
(или переиспользовать `file_id`) вместо публичного URL. Плюс альтернативный
способ сборки сообщения — массив `blocks` с классами `InputRichBlock*`
(включая `InputRichBlockSlideshow`).

Практическое следствие: галерея из картинок, доступных по публичному HTTP-URL,
работает на 10.1; галерея из **локальных файлов** (или переиспользование ранее
загруженных по `file_id`) требует 10.2 — только там есть `media` и
`tg://photo?id=`. Полный перечень изменений по версиям — в приложении внизу.

---

## Rich messages

The following methods and objects allow your bot to handle and send rich messages.

### Rich Message Formatting Options

[Rich messages](https://core.telegram.org/bots/api#inputrichmessage) support advanced structured formatting options like headings, lists, tables, media, block quotations, collapsible blocks, footnotes, and formulas. Telegram clients will render them accordingly. You can specify rich message content using [Markdown-style](https://core.telegram.org/bots/api#rich-markdown-style) or [HTML-style](https://core.telegram.org/bots/api#rich-html-style) formatting, or explicit [blocks](https://core.telegram.org/bots/api#inputrichblock).

Plain URLs, e-mail addresses, username mentions, hashtags, cashtags, bot commands, phone numbers, and bank card numbers are detected automatically. To disable automatic entity detection, pass _True_ in the _skip_entity_detection_ field. Note that Telegram clients will display an alert to the user before opening an inline link ('Open this link?' together with the full URL).

When [Markdown-style](https://core.telegram.org/bots/api#rich-markdown-style) or [HTML-style](https://core.telegram.org/bots/api#rich-html-style) formatting is used, you can use links in the form `tg://photo?id=...`, `tg://video?id=...`, and `tg://audio?id=...` instead of an HTTP URL to reuse previously uploaded files or upload a new file.

#### Rich Message Limits

Rich messages are subject to the following limits:
- Up to **32768 UTF-8 characters** in the rich message text, including custom emoji alternative text and formula source.
- Up to **500 blocks**, including nested blocks, list items, ordered list items, table rows, quotation blocks, and details blocks.
- Up to **16 levels** of nested formatting and blocks.
- Up to **50 media attachments** in total, including photos, videos, and audio files.
- Up to **20 columns** in a table.


#### Rich Markdown style

To use this mode, pass rich message content in the _markdown_ field. Use the following syntax in your message:

```
**bold text**
__bold text__
*italic text*
_italic text_
~~strikethrough text~~
`inline fixed-width code`
==marked text==
||spoiler||

[inline URL](https://t.me/)
[inline e-mail](mailto:user@example.com)
[inline phone number](tel:+123456789)
[inline mention of a user](tg://user?id=123456789)
![](tg://emoji?id=5368324170671202286)
![22:45 tomorrow](tg://time?unix=1647531900&format=wDT)
$x^2 + y^2$
\#hashtag $USD +12345678901, card: 4242 4242 4242 4242, https://t.me t.me a@t.me /command @username
all the text above was on the same line

# Heading 1
## Heading 2
### Heading 3
#### Heading 4
##### Heading 5
###### Heading 6

Paragraph text

```python
  print('pre-formatted fixed-width code block written in the Python programming language')
```

---

- unordered list item
* unordered list item
+ unordered list item

1. ordered list item
2. ordered list item

- [ ] task list item
- [x] completed task list item

>Block quotation started
>
>Block quotation continued on the next line
>Block quotation continued on the same line
>
>The last line of the block quotation

![](https://telegram.org/example/photo.jpg)
![](https://telegram.org/example/video.mp4)
![](https://telegram.org/example/audio.mp3)
![](https://telegram.org/example/audio.ogg)
![](https://telegram.org/example/animation.gif)

![](https://telegram.org/example/photo.jpg "Photo caption")
![](https://telegram.org/example/video.mp4 "Video caption")
![](https://telegram.org/example/audio.mp3 "Audio caption")
![](https://telegram.org/example/audio.ogg "Voice note caption")
![](https://telegram.org/example/animation.gif "Animation caption")

| Header 1 | Header 2 |
|:---------|:--------:|
| left     | center   |

Text with a reference[^id1] and another one[^id2].

[^id1]: Definition of the first footnote.
[^id2]: Definition of the second footnote.

$$E = mc^2$$

```math
E = mc^2
```

## Example Nested Syntax Report for _Q1_
Intro with <u>underlined text</u>, ==marked text==, and $x^2 + y^2$.
**Bold _italic <u>underlined italic bold</u> italic_ bold**
<u>In inline tags, nested **markdown** is parsed</u>
>Quote with **bold text, ~~strikethrough, and <tg-spoiler>spoiler</tg-spoiler>~~**, plus [a link](https://t.me/).

- List item with `code`, <sup>superscript</sup>, <sub>subscript</sub>, and a footnote[^note]
- Another item with **bold <tg-spoiler><code>spoiler code</code></tg-spoiler>**
- Another item with ~~strikethrough and <ins>inserted text</ins>~~

| Metric | Value |
|:-------|------:|
| Speed  | **42** <sup>ms</sup> |
| Status | <tg-spoiler>ready</tg-spoiler> |

[^note]: Footnote with _italic text_ and <u>HTML underline</u>.

---

# Details blocks can contain Markdown content:

<details open><summary>Summary with **bold text**</summary>

### Details heading
- List item with _italic text_
- List item with <tg-spoiler>spoiler</tg-spoiler>

</details>

# Collages and slideshows can contain Markdown media blocks:

<tg-collage>

![](https://telegram.org/example/photo.jpg)
![](https://telegram.org/example/video.mp4)

</tg-collage>

<tg-slideshow>

![](https://telegram.org/example/photo.jpg)
![](https://telegram.org/example/video.mp4)

</tg-slideshow>
```


For formatting features that don't have Markdown syntax, use [HTML tags](https://core.telegram.org/bots/api#rich-html-style):

```
<u>underlined text</u>, <ins>underlined text</ins>
<sub>subscript text</sub>
<sup>superscript text</sup>
<a name="chapter-1"></a>
<aside>Pull quote<cite>The Author</cite></aside>
<details open><summary>Title</summary>Content</details>
<tg-map lat="41.9" long="12.5" zoom="14"/>
<tg-collage><img src="https://telegram.org/example/photo.jpg"/><figcaption>Caption<cite>The Author</cite></figcaption></tg-collage>
<tg-slideshow><img src="https://telegram.org/example/photo.jpg"/><video src="https://telegram.org/example/video.mp4"/><figcaption>Slideshow caption<cite>The Author</cite></figcaption></tg-slideshow>
```


Additionally, you can use the following tag in [sendRichMessageDraft](https://core.telegram.org/bots/api#sendrichmessagedraft):

```
<tg-thinking>Thinking...</tg-thinking>
```


Please note:
- Rich Markdown is compatible with GitHub Flavored Markdown where possible and can contain arbitrary HTML. Supported rich message HTML tags are parsed as described in [Rich HTML style](https://core.telegram.org/bots/api#rich-html-style).
- Media can be specified only as a separate block.
- Media blocks support only HTTP and HTTPS URLs.
- Media type is determined by the MIME type and the URL of the media.
- In media syntax, the optional title after the URL is used as the caption; for example,  displays “Photo caption” under the media.
- Table cells can contain only inline formatting.
- Formula source is treated as raw LaTeX.
- Markdown isn't parsed inside block HTML tags other than <details>, <tg-collage> and <tg-slideshow>, therefore only HTML tags can be used there.
- See [date-time entity formatting](https://core.telegram.org/bots/api#date-time-entity-formatting) for more details about supported date-time formats.


#### Rich HTML style

To use this mode, pass rich message content in the _html_ field. The following tags are currently supported:

```
<a name="chapter-0"></a>
<b>bold text</b>, <strong>bold text</strong>
<i>italic text</i>, <em>italic text</em>
<u>underlined text</u>, <ins>underlined text</ins>
<s>strikethrough text</s>, <strike>strikethrough text</strike>, <del>strikethrough text</del>
<code>inline fixed-width code</code>
<mark>marked text</mark>
<sub>subscript text</sub>
<sup>superscript text</sup>
<tg-spoiler>spoiler</tg-spoiler>

<a href="#note-1">Reference</a>
<a href="https://t.me/">inline URL</a>
<a href="mailto:user@example.com">inline e-mail</a>
<a href="tel:+123456789">inline phone number</a>
<a href="tg://user?id=123456789">inline mention of a user</a>
<a href="#chapter-1">in-document link</a>
<a name="chapter-1"></a>

<tg-reference name="note-1">Referenced text</tg-reference>
<tg-emoji emoji-id="5368324170671202286"></tg-emoji>
<img src="tg://emoji?id=5368324170671202286" alt=""/>
<tg-time unix="1647531900" format="wDT">22:45 tomorrow</tg-time>
<tg-math>x^2 + y^2</tg-math>

#hashtag $USD +12345678901, card: 4242 4242 4242 4242, https://t.me t.me a@t.me /command @username

all the text above was on the same line

<h1>Heading 1</h1>
<h2>Heading 2</h2>
<h3>Heading 3</h3>
<h4>Heading 4</h4>
<h5>Heading 5</h5>
<h6>Heading 6</h6>

<a name="chapter-2"></a>

<p>Paragraph text</p>
<pre>pre-formatted fixed-width code block</pre>
<pre><code class="language-python">  print('pre-formatted fixed-width code block written in the Python programming language')</code></pre>
<footer>Footer text</footer>
<hr/>
<ul><li>unordered list item</li></ul>
<ol><li>ordered list item</li></ol>
<ol start="3" type="a" reversed><li>ordered list item</li></ol>
<ol><li value="7" type="i">ordered list item with explicit number</li></ol>
<ul>
<li><input type="checkbox" checked>Checked checkbox</li>
<li><input type="checkbox">Unchecked checkbox</li>
</ul>

<blockquote>Block quotation started<br>Block quotation continued<br>The last line of the block quotation<cite>The Author</cite></blockquote>
<aside>Pull quote<cite>The Author</cite></aside>

<img src="https://telegram.org/example/photo.jpg"/>
<video src="https://telegram.org/example/video.mp4"></video>
<audio src="https://telegram.org/example/audio.mp3"></audio>
<audio src="https://telegram.org/example/audio.ogg"></audio>
<video src="https://telegram.org/example/animation.gif"></video>

<figure><img src="https://telegram.org/example/photo.jpg" tg-spoiler/><figcaption>Photo caption<cite>Photo credit</cite></figcaption></figure>
<figure><video src="https://telegram.org/example/video.mp4" tg-spoiler></video><figcaption>Video caption</figcaption></figure>
<figure><audio src="https://telegram.org/example/audio.mp3"></audio><figcaption>Audio caption</figcaption></figure>
<figure><audio src="https://telegram.org/example/audio.ogg"></audio><figcaption>Voice note caption</figcaption></figure>
<figure><video src="https://telegram.org/example/animation.gif" tg-spoiler></video><figcaption>Animation caption</figcaption></figure>

<tg-map lat="41.9" long="12.5" zoom="14"/>
<figure><tg-map lat="41.9" long="12.5" zoom="14"/><figcaption>Map caption</figcaption></figure>

<tg-collage><img src="https://telegram.org/example/photo.jpg"/><video src="https://telegram.org/example/video.mp4"/></tg-collage>
<tg-collage><video src="https://telegram.org/example/video.mp4"/><img src="https://telegram.org/example/photo.jpg"/><figcaption>Collage caption</figcaption></tg-collage>
<tg-slideshow><img src="https://telegram.org/example/photo.jpg"/><video src="https://telegram.org/example/video.mp4"/></tg-slideshow>
<tg-slideshow><video src="https://telegram.org/example/video.mp4"/><img src="https://telegram.org/example/photo.jpg"/><figcaption>Slideshow caption</figcaption></tg-slideshow>

<table><tr><th>Header 1</th><th>Header 2</th></tr><tr><td>Value 1</td><td>Value 2</td></tr></table>
<table bordered striped><caption>Table caption</caption>
<tr><td colspan="2" rowspan="2" align="left">Value</td><td align="center">Value2</td><td align="right">Value3</td></tr>
<tr><td valign="top">Value4</td><td valign="middle">Value5</td><td valign="bottom">Value6</td></tr>
<tr><td>Value7</td></tr></table>

<details><summary>Title</summary>Content</details>
<details open><summary>Title</summary>Content</details>
<tg-math-block>E = mc^2</tg-math-block>
```


Additionally, you can use the following tag in [sendRichMessageDraft](https://core.telegram.org/bots/api#sendrichmessagedraft):

```
<tg-thinking>Thinking...</tg-thinking>
```


Please note:
- Only the tags mentioned above are currently supported.
- All numerical HTML entities are supported.
- The API currently supports only the following named HTML entities: `&lt;`, `&gt;`, `&amp;`, `&quot;`, `&apos;`, `&nbsp;`, `&hellip;`, `&mdash;`, `&ndash;`, `&lsquo;`, `&rsquo;`, `&ldquo;` and `&rdquo;`.
- Use nested `pre` and `code` tags to define the programming language for a pre-formatted block.
- Programming language can't be specified for standalone `code` tags.
- Links `mailto:...`, `tel:...`, and `tg://user?id=...` are rendered as e-mail links, phone links, and inline mentions respectively. Other supported links are rendered as regular inline links.
- Images, videos, and audio files can be specified only as separate media blocks.
- Media blocks support only HTTP and HTTPS URLs.
- An empty `<a name="..."></a>` on its own creates an anchor that can be linked to with `<a href="#...">...</a>`.
- In `<figcaption>`, you can use `<cite>` tags to specify caption credit.
- Use `<tg-reference name="...">...</tg-reference>` to define referenced text that can be linked to with `<a href="#...">...</a>`.
- The body of a `<details>` tag can contain rich message content. If the `open` attribute is specified, the block is expanded by default.
- Formula source is treated as raw LaTeX.
- See [date-time entity formatting](https://core.telegram.org/bots/api#date-time-entity-formatting) for more details about supported date-time formats.


### RichMessage

Rich formatted message.


| Field | Type | Description |
|---|---|---|
| blocks | Array of [RichBlock](https://core.telegram.org/bots/api#richblock) | Content of the message |
| is_rtl | Boolean | _Optional_. _True_, if the rich message must be shown right-to-left |


### InputRichMessage

Describes a rich message to be sent. Exactly **one** of the fields _html_, _markdown_, or _blocks_ must be used.


| Field | Type | Description |
|---|---|---|
| blocks | Array of [InputRichBlock](https://core.telegram.org/bots/api#inputrichblock) | _Optional_. Content of the rich message to send described as a list of blocks |
| html | String | _Optional_. Content of the rich message to send described using HTML formatting. See [rich message formatting options](https://core.telegram.org/bots/api#rich-message-formatting-options) for more details. Use _media_ field to specify the media used in the message. |
| markdown | String | _Optional_. Content of the rich message to send described using Markdown formatting. See [rich message formatting options](https://core.telegram.org/bots/api#rich-message-formatting-options) for more details. Use _media_ field to specify the media used in the message. |
| media | Array of [InputRichMessageMedia](https://core.telegram.org/bots/api#inputrichmessagemedia) | _Optional_. List of media that are specified in the _markdown_ or _html_ fields using `tg://photo?id=`, `tg://video?id=`, and `tg://audio?id=` links |
| is_rtl | Boolean | _Optional_. Pass _True_ if the rich message must be shown right-to-left |
| skip_entity_detection | Boolean | _Optional_. Pass _True_ to skip automatic detection of entities (e.g., URLs, email addresses, username mentions, hashtags, cashtags, bot commands, or phone numbers) in the text |


### InputRichMessageMedia

Describes a media element embedded in an outgoing rich message.


| Field | Type | Description |
|---|---|---|
| id | String | Unique identifier of the media used in a `tg://photo?id=`, `tg://video?id=`, or `tg://audio?id=` link. 1-64 characters, only `A-Z`, `a-z`, `0-9`, `_` and `-` are allowed. |
| media | [InputMediaAnimation](https://core.telegram.org/bots/api#inputmediaanimation) or [InputMediaAudio](https://core.telegram.org/bots/api#inputmediaaudio) or [InputMediaPhoto](https://core.telegram.org/bots/api#inputmediaphoto) or [InputMediaVideo](https://core.telegram.org/bots/api#inputmediavideo) or [InputMediaVoiceNote](https://core.telegram.org/bots/api#inputmediavoicenote) | The media to be sent. Everything except the media itself and its properties is ignored. |


### sendRichMessage

Use this method to send rich messages. If the message contains a block with a media element, then the bot must have the right to send the media to the chat. On success, the sent [Message](https://core.telegram.org/bots/api#message) is returned.


| Parameter | Type | Required | Description |
|---|---|---|---|
| business_connection_id | String | Optional | Unique identifier of the business connection on behalf of which the message will be sent. Bot can send rich messages on behalf of a business account only if the corresponding user can send rich messages. |
| chat_id | Integer or String | Yes | Unique identifier for the target chat or username of the target bot, supergroup or channel in the format `@username` |
| message_thread_id | Integer | Optional | Unique identifier for the target message thread (topic) of a forum; for forum supergroups and private chats of bots with forum topic mode enabled only |
| direct_messages_topic_id | Integer | Optional | Identifier of the direct messages topic to which the message will be sent; required if the message is sent to a direct messages chat |
| rich_message | [InputRichMessage](https://core.telegram.org/bots/api#inputrichmessage) | Yes | The message to be sent |
| disable_notification | Boolean | Optional | Sends the message [silently](https://telegram.org/blog/channels-2-0#silent-messages). Users will receive a notification with no sound. |
| protect_content | Boolean | Optional | Protects the contents of the sent message from forwarding and saving |
| allow_paid_broadcast | Boolean | Optional | Pass _True_ to allow up to 1000 messages per second, ignoring [broadcasting limits](https://core.telegram.org/bots/faq#how-can-i-message-all-of-my-bot-39s-subscribers-at-once) for a fee of 0.1 Telegram Stars per message. The relevant Stars will be withdrawn from the bot's balance. |
| message_effect_id | String | Optional | Unique identifier of the message effect to be added to the message; for private chats only |
| suggested_post_parameters | [SuggestedPostParameters](https://core.telegram.org/bots/api#suggestedpostparameters) | Optional | A JSON-serialized object containing the parameters of the suggested post to send; for direct messages chats only. If the message is sent as a reply to another suggested post, then that suggested post is automatically declined. |
| reply_parameters | [ReplyParameters](https://core.telegram.org/bots/api#replyparameters) | Optional | Description of the message to reply to |
| reply_markup | [InlineKeyboardMarkup](https://core.telegram.org/bots/api#inlinekeyboardmarkup) or [ReplyKeyboardMarkup](https://core.telegram.org/bots/api#replykeyboardmarkup) or [ReplyKeyboardRemove](https://core.telegram.org/bots/api#replykeyboardremove) or [ForceReply](https://core.telegram.org/bots/api#forcereply) | Optional | Additional interface options. A JSON-serialized object for an [inline keyboard](https://core.telegram.org/bots/features#inline-keyboards), [custom reply keyboard](https://core.telegram.org/bots/features#keyboards), instructions to remove a reply keyboard or to force a reply from the user. |


### sendRichMessageDraft

Use this method to stream a partial rich message to a user while the message is being generated. Note that the streamed draft is ephemeral and acts as a temporary 30-second preview - once the output is finalized, you **must** call [sendRichMessage](https://core.telegram.org/bots/api#sendrichmessage) with the complete message to persist it in the user's chat. Returns _True_ on success.


| Parameter | Type | Required | Description |
|---|---|---|---|
| chat_id | Integer | Yes | Unique identifier for the target private chat |
| message_thread_id | Integer | Optional | Unique identifier for the target message thread |
| draft_id | Integer | Yes | Unique identifier of the message draft; must be non-zero. Changes to drafts with the same identifier are animated. |
| rich_message | [InputRichMessage](https://core.telegram.org/bots/api#inputrichmessage) | Yes | The partial message to be streamed. Direct upload of new files isn't supported. |


### RichText

This object represents a rich formatted text. Currently, it can be either a String for plain text, an Array of [RichText](https://core.telegram.org/bots/api#richtext), or any of the following types:
- [RichTextBold](https://core.telegram.org/bots/api#richtextbold)
- [RichTextItalic](https://core.telegram.org/bots/api#richtextitalic)
- [RichTextUnderline](https://core.telegram.org/bots/api#richtextunderline)
- [RichTextStrikethrough](https://core.telegram.org/bots/api#richtextstrikethrough)
- [RichTextSpoiler](https://core.telegram.org/bots/api#richtextspoiler)
- [RichTextDateTime](https://core.telegram.org/bots/api#richtextdatetime)
- [RichTextTextMention](https://core.telegram.org/bots/api#richtexttextmention)
- [RichTextSubscript](https://core.telegram.org/bots/api#richtextsubscript)
- [RichTextSuperscript](https://core.telegram.org/bots/api#richtextsuperscript)
- [RichTextMarked](https://core.telegram.org/bots/api#richtextmarked)
- [RichTextCode](https://core.telegram.org/bots/api#richtextcode)
- [RichTextCustomEmoji](https://core.telegram.org/bots/api#richtextcustomemoji)
- [RichTextMathematicalExpression](https://core.telegram.org/bots/api#richtextmathematicalexpression)
- [RichTextUrl](https://core.telegram.org/bots/api#richtexturl)
- [RichTextEmailAddress](https://core.telegram.org/bots/api#richtextemailaddress)
- [RichTextPhoneNumber](https://core.telegram.org/bots/api#richtextphonenumber)
- [RichTextBankCardNumber](https://core.telegram.org/bots/api#richtextbankcardnumber)
- [RichTextMention](https://core.telegram.org/bots/api#richtextmention)
- [RichTextHashtag](https://core.telegram.org/bots/api#richtexthashtag)
- [RichTextCashtag](https://core.telegram.org/bots/api#richtextcashtag)
- [RichTextBotCommand](https://core.telegram.org/bots/api#richtextbotcommand)
- [RichTextAnchor](https://core.telegram.org/bots/api#richtextanchor)
- [RichTextAnchorLink](https://core.telegram.org/bots/api#richtextanchorlink)
- [RichTextReference](https://core.telegram.org/bots/api#richtextreference)
- [RichTextReferenceLink](https://core.telegram.org/bots/api#richtextreferencelink)


### RichTextBold

A bold text.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “bold” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The text |


### RichTextItalic

An italicized text.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “italic” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The text |


### RichTextUnderline

An underlined text.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “underline” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The text |


### RichTextStrikethrough

A strikethrough text.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “strikethrough” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The text |


### RichTextSpoiler

A text covered by a spoiler.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “spoiler” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The text |


### RichTextDateTime

Formatted date and time.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “date_time” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The text |
| unix_time | Integer | The Unix time associated with the entity |
| date_time_format | String | The string that defines the formatting of the date and time. See [date-time entity formatting](https://core.telegram.org/bots/api#date-time-entity-formatting) for more details. |


### RichTextTextMention

A mention of a Telegram user by their identifier.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “text_mention” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The text |
| user | [User](https://core.telegram.org/bots/api#user) | The mentioned user |


### RichTextSubscript

A subscript text.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “subscript” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The text |


### RichTextSuperscript

A superscript text.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “superscript” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The text |


### RichTextMarked

A marked text.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “marked” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The text |


### RichTextCode

A monowidth text.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “code” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The text |


### RichTextCustomEmoji

A custom emoji.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “custom_emoji” |
| custom_emoji_id | String | Unique identifier of the custom emoji. Use [getCustomEmojiStickers](https://core.telegram.org/bots/api#getcustomemojistickers) to get full information about the sticker. |
| alternative_text | String | Alternative emoji for the custom emoji |


### RichTextMathematicalExpression

A mathematical expression.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “mathematical_expression” |
| expression | String | The expression in LaTeX format |


### RichTextUrl

A text with a link.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “url” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The text |
| url | String | URL of the link |


### RichTextEmailAddress

A text with an email address.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “email_address” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The text |
| email_address | String | The email address |


### RichTextPhoneNumber

A text with a phone number.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “phone_number” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The text |
| phone_number | String | The phone number |


### RichTextBankCardNumber

A text with a bank card number.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “bank_card_number” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The text |
| bank_card_number | String | The bank card number |


### RichTextMention

A mention by a username.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “mention” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The text |
| username | String | The username |


### RichTextHashtag

A hashtag.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “hashtag” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The text |
| hashtag | String | The hashtag |


### RichTextCashtag

A cashtag.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “cashtag” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The text |
| cashtag | String | The cashtag |


### RichTextBotCommand

A bot command.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “bot_command” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The text |
| bot_command | String | The bot command |


### RichTextAnchor

An anchor.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “anchor” |
| name | String | The name of the anchor |


### RichTextAnchorLink

A link to an anchor.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “anchor_link” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The link text |
| anchor_name | String | The name of the anchor. If the name is empty, then the link brings back to the top of the message. |


### RichTextReference

A reference.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “reference” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | Text of the reference |
| name | String | The name of the reference |


### RichTextReferenceLink

A link to a reference.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the rich text, always “reference_link” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | The link text |
| reference_name | String | The name of the reference |


### RichBlockCaption

Caption of a rich formatted block.


| Field | Type | Description |
|---|---|---|
| text | [RichText](https://core.telegram.org/bots/api#richtext) | Block caption |
| credit | [RichText](https://core.telegram.org/bots/api#richtext) | _Optional_. Block credit which corresponds to the HTML tag <cite> |


### RichBlockTableCell

Cell in a table.


| Field | Type | Description |
|---|---|---|
| text | [RichText](https://core.telegram.org/bots/api#richtext) | _Optional_. Text in the cell. If omitted, then the cell is invisible. |
| is_header | True | _Optional_. _True_, if the cell is a header cell |
| colspan | Integer | _Optional_. The number of columns the cell spans if it is bigger than 1 |
| rowspan | Integer | _Optional_. The number of rows the cell spans if it is bigger than 1 |
| align | String | Horizontal cell content alignment. Currently, must be one of “left”, “center”, or “right”. |
| valign | String | Vertical cell content alignment. Currently, must be one of “top”, “middle”, or “bottom”. |


### RichBlockListItem

An item of a list.


| Field | Type | Description |
|---|---|---|
| label | String | Label of the item |
| blocks | Array of [RichBlock](https://core.telegram.org/bots/api#richblock) | The content of the item |
| has_checkbox | True | _Optional_. _True_, if the item has a checkbox |
| is_checked | True | _Optional_. _True_, if the item has a checked checkbox |
| value | Integer | _Optional_. For ordered lists, the numeric value of the item label |
| type | String | _Optional_. For ordered lists, the type of the item label; must be one of “a” for lowercase letters, “A” for uppercase letters, “i” for lowercase Roman numerals, “I” for uppercase Roman numerals, or “1” for decimal numbers |


### RichBlock

This object represents a block in a rich formatted message. Currently, it can be any of the following types:
- [RichBlockParagraph](https://core.telegram.org/bots/api#richblockparagraph)
- [RichBlockSectionHeading](https://core.telegram.org/bots/api#richblocksectionheading)
- [RichBlockPreformatted](https://core.telegram.org/bots/api#richblockpreformatted)
- [RichBlockFooter](https://core.telegram.org/bots/api#richblockfooter)
- [RichBlockDivider](https://core.telegram.org/bots/api#richblockdivider)
- [RichBlockMathematicalExpression](https://core.telegram.org/bots/api#richblockmathematicalexpression)
- [RichBlockAnchor](https://core.telegram.org/bots/api#richblockanchor)
- [RichBlockList](https://core.telegram.org/bots/api#richblocklist)
- [RichBlockBlockQuotation](https://core.telegram.org/bots/api#richblockblockquotation)
- [RichBlockPullQuotation](https://core.telegram.org/bots/api#richblockpullquotation)
- [RichBlockCollage](https://core.telegram.org/bots/api#richblockcollage)
- [RichBlockSlideshow](https://core.telegram.org/bots/api#richblockslideshow)
- [RichBlockTable](https://core.telegram.org/bots/api#richblocktable)
- [RichBlockDetails](https://core.telegram.org/bots/api#richblockdetails)
- [RichBlockMap](https://core.telegram.org/bots/api#richblockmap)
- [RichBlockAnimation](https://core.telegram.org/bots/api#richblockanimation)
- [RichBlockAudio](https://core.telegram.org/bots/api#richblockaudio)
- [RichBlockPhoto](https://core.telegram.org/bots/api#richblockphoto)
- [RichBlockVideo](https://core.telegram.org/bots/api#richblockvideo)
- [RichBlockVoiceNote](https://core.telegram.org/bots/api#richblockvoicenote)
- [RichBlockThinking](https://core.telegram.org/bots/api#richblockthinking)


### RichBlockParagraph

A text paragraph, corresponding to the HTML tag `<p>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “paragraph” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | Text of the block |


### RichBlockSectionHeading

A section heading, corresponding to the HTML tags `<h1>`, `<h2>`, `<h3>`, `<h4>`, `<h5>`, or `<h6>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “heading” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | Text of the block |
| size | Integer | Relative size of the text font; 1-6, 1 is the largest, 6 is the smallest |


### RichBlockPreformatted

A preformatted text block, corresponding to the nested HTML tags `<pre>` and `<code>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “pre” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | Text of the block |
| language | String | _Optional_. The programming language of the text |


### RichBlockFooter

A footer, corresponding to the HTML tag `<footer>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “footer” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | Text of the block |


### RichBlockDivider

A divider, corresponding to the HTML tag `<hr/>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “divider” |


### RichBlockMathematicalExpression

A block with a mathematical expression in LaTeX format, corresponding to the custom HTML tag `<tg-math-block>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “mathematical_expression” |
| expression | String | The mathematical expression in LaTeX format |


### RichBlockAnchor

A block with an anchor, corresponding to the HTML tag `<a>` with the attribute `name`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “anchor” |
| name | String | The name of the anchor |


### RichBlockList

A list of blocks, corresponding to the HTML tag `<ul>` or `<ol>` with multiple nested tags `<li>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “list” |
| items | Array of [RichBlockListItem](https://core.telegram.org/bots/api#richblocklistitem) | Items of the list |


### RichBlockBlockQuotation

A block quotation, corresponding to the HTML tag `<blockquote>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “blockquote” |
| blocks | Array of [RichBlock](https://core.telegram.org/bots/api#richblock) | Content of the block |
| credit | [RichText](https://core.telegram.org/bots/api#richtext) | _Optional_. Credit of the block |


### RichBlockPullQuotation

A quotation with centered text, loosely corresponding to the HTML tag `<aside>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “pullquote” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | Text of the block |
| credit | [RichText](https://core.telegram.org/bots/api#richtext) | _Optional_. Credit of the block |


### RichBlockCollage

A collage, corresponding to the custom HTML tag `<tg-collage>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “collage” |
| blocks | Array of [RichBlock](https://core.telegram.org/bots/api#richblock) | Elements of the collage |
| caption | [RichBlockCaption](https://core.telegram.org/bots/api#richblockcaption) | _Optional_. Caption of the block |


### RichBlockSlideshow

A slideshow, corresponding to the custom HTML tag `<tg-slideshow>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “slideshow” |
| blocks | Array of [RichBlock](https://core.telegram.org/bots/api#richblock) | Elements of the slideshow |
| caption | [RichBlockCaption](https://core.telegram.org/bots/api#richblockcaption) | _Optional_. Caption of the block |


### RichBlockTable

A table, corresponding to the HTML tag `<table>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “table” |
| cells | Array of Array of [RichBlockTableCell](https://core.telegram.org/bots/api#richblocktablecell) | Cells of the table |
| is_bordered | True | _Optional_. _True_, if the table has borders |
| is_striped | True | _Optional_. _True_, if the table is striped |
| caption | [RichText](https://core.telegram.org/bots/api#richtext) | _Optional_. Caption of the table |


### RichBlockDetails

An expandable block for details disclosure, corresponding to the HTML tag `<details>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “details” |
| summary | [RichText](https://core.telegram.org/bots/api#richtext) | Always shown summary of the block |
| blocks | Array of [RichBlock](https://core.telegram.org/bots/api#richblock) | Content of the block |
| is_open | True | _Optional_. _True_, if the content of the block is visible by default |


### RichBlockMap

A block with a map, corresponding to the custom HTML tag `<tg-map>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “map” |
| location | [Location](https://core.telegram.org/bots/api#location) | Location of the center of the map |
| zoom | Integer | Map zoom level; 13-20 |
| width | Integer | Expected width of the map |
| height | Integer | Expected height of the map |
| caption | [RichBlockCaption](https://core.telegram.org/bots/api#richblockcaption) | _Optional_. Caption of the block |


### RichBlockAnimation

A block with an animation, corresponding to the HTML tag `<video>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “animation” |
| animation | [Animation](https://core.telegram.org/bots/api#animation) | The animation |
| has_spoiler | True | _Optional_. _True_, if the media preview is covered by a spoiler animation |
| caption | [RichBlockCaption](https://core.telegram.org/bots/api#richblockcaption) | _Optional_. Caption of the block |


### RichBlockAudio

A block with a music file, corresponding to the HTML tag `<audio>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “audio” |
| audio | [Audio](https://core.telegram.org/bots/api#audio) | The audio |
| caption | [RichBlockCaption](https://core.telegram.org/bots/api#richblockcaption) | _Optional_. Caption of the block |


### RichBlockPhoto

A block with a photo, corresponding to the HTML tag `<img>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “photo” |
| photo | Array of [PhotoSize](https://core.telegram.org/bots/api#photosize) | Available sizes of the photo |
| has_spoiler | True | _Optional_. _True_, if the media preview is covered by a spoiler animation |
| caption | [RichBlockCaption](https://core.telegram.org/bots/api#richblockcaption) | _Optional_. Caption of the block |


### RichBlockVideo

A block with a video, corresponding to the HTML tag `<video>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “video” |
| video | [Video](https://core.telegram.org/bots/api#video) | The video |
| has_spoiler | True | _Optional_. _True_, if the media preview is covered by a spoiler animation |
| caption | [RichBlockCaption](https://core.telegram.org/bots/api#richblockcaption) | _Optional_. Caption of the block |


### RichBlockVoiceNote

A block with a voice note, corresponding to the HTML tag `<audio>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “voice_note” |
| voice_note | [Voice](https://core.telegram.org/bots/api#voice) | The voice note |
| caption | [RichBlockCaption](https://core.telegram.org/bots/api#richblockcaption) | _Optional_. Caption of the block |


### RichBlockThinking

A block with a “Thinking…” placeholder, corresponding to the custom HTML tag `<tg-thinking>`. The block may be used only in [sendRichMessageDraft](https://core.telegram.org/bots/api#sendrichmessagedraft), therefore it can't be received in messages. See [[https://t.me/addemoji/AIActions](https://t.me/addemoji/AIActions)] for examples of custom emoji that are recommended for usage in the block.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “thinking” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | Text of the block. See [[https://t.me/addemoji/AIActions](https://t.me/addemoji/AIActions)] for examples of custom emoji that are recommended for usage in the block. |


### InputRichBlockListItem

An item of a list to be sent.


| Field | Type | Description |
|---|---|---|
| blocks | Array of [InputRichBlock](https://core.telegram.org/bots/api#inputrichblock) | The content of the item |
| has_checkbox | True | _Optional_. Pass _True_ if the item has a checkbox |
| is_checked | True | _Optional_. Pass _True_ if the item has a checked checkbox |
| value | Integer | _Optional_. For ordered lists, the numeric value of the item label |
| type | String | _Optional_. For ordered lists, the type of the item label; must be one of “a” for lowercase letters, “A” for uppercase letters, “i” for lowercase Roman numerals, “I” for uppercase Roman numerals, or “1” for decimal numbers |


### InputRichBlock

This object represents a block in a rich formatted message to be sent. Currently, it can be any of the following types:
- [InputRichBlockParagraph](https://core.telegram.org/bots/api#inputrichblockparagraph)
- [InputRichBlockSectionHeading](https://core.telegram.org/bots/api#inputrichblocksectionheading)
- [InputRichBlockPreformatted](https://core.telegram.org/bots/api#inputrichblockpreformatted)
- [InputRichBlockFooter](https://core.telegram.org/bots/api#inputrichblockfooter)
- [InputRichBlockDivider](https://core.telegram.org/bots/api#inputrichblockdivider)
- [InputRichBlockMathematicalExpression](https://core.telegram.org/bots/api#inputrichblockmathematicalexpression)
- [InputRichBlockAnchor](https://core.telegram.org/bots/api#inputrichblockanchor)
- [InputRichBlockList](https://core.telegram.org/bots/api#inputrichblocklist)
- [InputRichBlockBlockQuotation](https://core.telegram.org/bots/api#inputrichblockblockquotation)
- [InputRichBlockPullQuotation](https://core.telegram.org/bots/api#inputrichblockpullquotation)
- [InputRichBlockCollage](https://core.telegram.org/bots/api#inputrichblockcollage)
- [InputRichBlockSlideshow](https://core.telegram.org/bots/api#inputrichblockslideshow)
- [InputRichBlockTable](https://core.telegram.org/bots/api#inputrichblocktable)
- [InputRichBlockDetails](https://core.telegram.org/bots/api#inputrichblockdetails)
- [InputRichBlockMap](https://core.telegram.org/bots/api#inputrichblockmap)
- [InputRichBlockAnimation](https://core.telegram.org/bots/api#inputrichblockanimation)
- [InputRichBlockAudio](https://core.telegram.org/bots/api#inputrichblockaudio)
- [InputRichBlockPhoto](https://core.telegram.org/bots/api#inputrichblockphoto)
- [InputRichBlockVideo](https://core.telegram.org/bots/api#inputrichblockvideo)
- [InputRichBlockVoiceNote](https://core.telegram.org/bots/api#inputrichblockvoicenote)
- [InputRichBlockThinking](https://core.telegram.org/bots/api#inputrichblockthinking)


### InputRichBlockParagraph

A text paragraph, corresponding to the HTML tag `<p>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “paragraph” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | Text of the block |


### InputRichBlockSectionHeading

A section heading, corresponding to the HTML tags `<h1>`, `<h2>`, `<h3>`, `<h4>`, `<h5>`, or `<h6>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “heading” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | Text of the block |
| size | Integer | Relative size of the text font; 1-6, 1 is the largest, 6 is the smallest |


### InputRichBlockPreformatted

A preformatted text block, corresponding to the nested HTML tags `<pre>` and `<code>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “pre” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | Text of the block |
| language | String | _Optional_. The programming language of the text |


### InputRichBlockFooter

A footer, corresponding to the HTML tag `<footer>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “footer” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | Text of the block |


### InputRichBlockDivider

A divider, corresponding to the HTML tag `<hr/>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “divider” |


### InputRichBlockMathematicalExpression

A block with a mathematical expression in LaTeX format, corresponding to the custom HTML tag `<tg-math-block>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “mathematical_expression” |
| expression | String | The mathematical expression in LaTeX format |


### InputRichBlockAnchor

A block with an anchor, corresponding to the HTML tag `<a>` with the attribute `name`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “anchor” |
| name | String | The name of the anchor |


### InputRichBlockList

A list of blocks, corresponding to the HTML tag `<ul>` or `<ol>` with multiple nested tags `<li>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “list” |
| items | Array of [InputRichBlockListItem](https://core.telegram.org/bots/api#inputrichblocklistitem) | Items of the list |


### InputRichBlockBlockQuotation

A block quotation, corresponding to the HTML tag `<blockquote>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “blockquote” |
| blocks | Array of [InputRichBlock](https://core.telegram.org/bots/api#inputrichblock) | Content of the block |
| credit | [RichText](https://core.telegram.org/bots/api#richtext) | _Optional_. Credit of the block |


### InputRichBlockPullQuotation

A quotation with centered text, loosely corresponding to the HTML tag `<aside>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “pullquote” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | Text of the block |
| credit | [RichText](https://core.telegram.org/bots/api#richtext) | _Optional_. Credit of the block |


### InputRichBlockCollage

A collage, corresponding to the custom HTML tag `<tg-collage>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “collage” |
| blocks | Array of [InputRichBlock](https://core.telegram.org/bots/api#inputrichblock) | Elements of the collage |
| caption | [RichBlockCaption](https://core.telegram.org/bots/api#richblockcaption) | _Optional_. Caption of the block |


### InputRichBlockSlideshow

A slideshow, corresponding to the custom HTML tag `<tg-slideshow>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “slideshow” |
| blocks | Array of [InputRichBlock](https://core.telegram.org/bots/api#inputrichblock) | Elements of the slideshow |
| caption | [RichBlockCaption](https://core.telegram.org/bots/api#richblockcaption) | _Optional_. Caption of the block |


### InputRichBlockTable

A table, corresponding to the HTML tag `<table>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “table” |
| cells | Array of Array of [RichBlockTableCell](https://core.telegram.org/bots/api#richblocktablecell) | Cells of the table |
| is_bordered | True | _Optional_. Pass _True_ if the table has borders |
| is_striped | True | _Optional_. Pass _True_ if the table is striped |
| caption | [RichText](https://core.telegram.org/bots/api#richtext) | _Optional_. Caption of the table |


### InputRichBlockDetails

An expandable block for details disclosure, corresponding to the HTML tag `<details>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “details” |
| summary | [RichText](https://core.telegram.org/bots/api#richtext) | Always shown summary of the block |
| blocks | Array of [InputRichBlock](https://core.telegram.org/bots/api#inputrichblock) | Content of the block |
| is_open | True | _Optional_. Pass _True_ if the content of the block is visible by default |


### InputRichBlockMap

A block with a map, corresponding to the custom HTML tag `<tg-map>`. The map's width and height must not exceed 10000 in total. The width and height ratio must be at most 20.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “map” |
| location | [Location](https://core.telegram.org/bots/api#location) | Location of the center of the map |
| zoom | Integer | Map zoom level; 0-24 |
| width | Integer | Map width; 0-10000 |
| height | Integer | Map height; 0-10000 |
| caption | [RichBlockCaption](https://core.telegram.org/bots/api#richblockcaption) | _Optional_. Caption of the block |


### InputRichBlockAnimation

A block with an animation, corresponding to the HTML tag `<video>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “animation” |
| animation | [InputMediaAnimation](https://core.telegram.org/bots/api#inputmediaanimation) | The animation. Caption is ignored. |
| caption | [RichBlockCaption](https://core.telegram.org/bots/api#richblockcaption) | _Optional_. Caption of the block |


### InputRichBlockAudio

A block with a music file, corresponding to the HTML tag `<audio>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “audio” |
| audio | [InputMediaAudio](https://core.telegram.org/bots/api#inputmediaaudio) | The audio. Caption is ignored. |
| caption | [RichBlockCaption](https://core.telegram.org/bots/api#richblockcaption) | _Optional_. Caption of the block |


### InputRichBlockPhoto

A block with a photo, corresponding to the HTML tag `<img>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “photo” |
| photo | [InputMediaPhoto](https://core.telegram.org/bots/api#inputmediaphoto) | The photo. Caption is ignored. |
| caption | [RichBlockCaption](https://core.telegram.org/bots/api#richblockcaption) | _Optional_. Caption of the block |


### InputRichBlockVideo

A block with a video, corresponding to the HTML tag `<video>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “video” |
| video | [InputMediaVideo](https://core.telegram.org/bots/api#inputmediavideo) | The video. Caption is ignored. |
| caption | [RichBlockCaption](https://core.telegram.org/bots/api#richblockcaption) | _Optional_. Caption of the block |


### InputRichBlockVoiceNote

A block with a voice note, corresponding to the HTML tag `<audio>`.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “voice_note” |
| voice_note | [InputMediaVoiceNote](https://core.telegram.org/bots/api#inputmediavoicenote) | The voice note. Caption is ignored. |
| caption | [RichBlockCaption](https://core.telegram.org/bots/api#richblockcaption) | _Optional_. Caption of the block |


### InputRichBlockThinking

A block with a “Thinking…” placeholder, corresponding to the custom HTML tag `<tg-thinking>`. The block may be used only in [sendRichMessageDraft](https://core.telegram.org/bots/api#sendrichmessagedraft), therefore it can't be received in messages. See [[https://t.me/addemoji/AIActions](https://t.me/addemoji/AIActions)] for examples of custom emoji that are recommended for usage in the block.


| Field | Type | Description |
|---|---|---|
| type | String | Type of the block, always “thinking” |
| text | [RichText](https://core.telegram.org/bots/api#richtext) | Text of the block. See [[https://t.me/addemoji/AIActions](https://t.me/addemoji/AIActions)] for examples of custom emoji that are recommended for usage in the block. |

### InputRichMessageContent

Represents the [content](https://core.telegram.org/bots/api#inputmessagecontent) of a rich message to be sent as the result of an inline query.


| Field | Type | Description |
|---|---|---|
| rich_message | [InputRichMessage](https://core.telegram.org/bots/api#inputrichmessage) | The message to be sent |

---

## Приложение: что появилось в каких версиях


### Bot API 10.2 — 14 июля 2026

- Added the class InputRichMessageMedia and the field media to the class InputRichMessage, allowing bots to explicitly specify media used in markdown or html formatting when sending a rich message.
- Added the class InputRichBlockListItem, which represents an item in a list to be sent.
- Added the classes InputRichBlockParagraph, InputRichBlockSectionHeading, InputRichBlockPreformatted, InputRichBlockFooter, InputRichBlockDivider, InputRichBlockMathematicalExpression, InputRichBlockAnchor, InputRichBlockList, InputRichBlockBlockQuotation, InputRichBlockPullQuotation, InputRichBlockCollage, InputRichBlockSlideshow, InputRichBlockTable, InputRichBlockDetails, InputRichBlockMap, InputRichBlockAnimation, InputRichBlockAudio, InputRichBlockPhoto, InputRichBlockVideo, InputRichBlockVoiceNote and InputRichBlockThinking, which represent different types of blocks available to format an outgoing rich message.
- Added the field blocks to the class InputRichMessage, allowing bots to specify rich message formatting via block entities.


### Bot API 10.1 — 11 июня 2026

- Added support for Rich Messages, allowing bots to send highly structured text and stream AI-generated replies with seamless rich formatting.
- Added the classes RichTextBold, RichTextItalic, RichTextUnderline, RichTextStrikethrough, RichTextSpoiler, RichTextDateTime, RichTextTextMention, RichTextSubscript, RichTextSuperscript, RichTextMarked, RichTextCode, RichTextCustomEmoji, RichTextMathematicalExpression, RichTextUrl, RichTextEmailAddress, RichTextPhoneNumber, RichTextBankCardNumber, RichTextMention, RichTextHashtag, RichTextCashtag, RichTextBotCommand, RichTextAnchor, RichTextAnchorLink, RichTextReference and RichTextReferenceLink, which represent different types of rich formatted text.
- Added the class RichText, which represents rich formatted text.
- Added the class RichBlockCaption, which represents the caption of a rich formatted text.
- Added the class RichBlockTableCell, which represents a cell in a table.
- Added the class RichBlockListItem, which represents an item in a list.
- Added the classes RichBlockParagraph, RichBlockSectionHeading, RichBlockPreformatted, RichBlockFooter, RichBlockDivider, RichBlockMathematicalExpression, RichBlockAnchor, RichBlockList, RichBlockBlockQuotation, RichBlockPullQuotation, RichBlockCollage, RichBlockSlideshow, RichBlockTable, RichBlockDetails, RichBlockMap, RichBlockAnimation, RichBlockAudio, RichBlockPhoto, RichBlockVideo, RichBlockVoiceNote and RichBlockThinking, which represent different types of blocks in a rich formatted message.
- Added the class RichBlock, which represents a block in a rich formatted message.
- Added the class RichMessage, which represents a rich formatted message.
- Added the field rich_message to the class Message.
- Added the class InputRichMessage, describing a rich message to send.
- Added the class InputRichMessageContent and allowed it to be used as InputMessageContent in results of inline, guest, and Web App queries.
- Added the method sendRichMessage, allowing bots to send rich messages.
- Added the method sendRichMessageDraft, allowing bots to stream partial rich messages.
- Added the parameter rich_message to the method editMessageText, allowing bots to edit rich messages.
