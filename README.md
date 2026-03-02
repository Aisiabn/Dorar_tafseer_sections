# # موسوعة التفسير — مُنظَّمة موضوعياً

استخراج وتنظيم محتوى **موسوعة التفسير** من [dorar.net](https://dorar.net/tafseer) بصيغة Markdown قابلة للبحث والمشاركة.

---

## المحتوى

المخرجات في مجلد `dorar_tafseer_output/` مقسّمة إلى فرعين:

| المجلد | الوصف |
|--------|-------|
| `by_section/` | ملف لكل **نوع قسم** (غريب الكلمات، تفسير الآيات، الفوائد...) يجمع المادة من جميع السور |
| `tafseer_sections/` | ملف لكل **عنوان فرعي** (title-1) مُجمَّع عبر السور |

---

## هيكل الملفات

```
Dorar_tafseer_sections/
├── dorar_tafseer_output/
│   ├── by_section/
│   │   ├── فهرس.md
│   │   ├── غريب_الكلمات.md
│   │   ├── تفسير_الآيات.md
│   │   └── ...
│   └── tafseer_sections/
│       ├── مناسبة_الآيات.md
│       ├── الفوائد_التربوية.md
│       └── ...
├── scraper_sections.py
├── .github/
│   └── workflows/
│       └── scrape_sections.yml
└── README.md
```

---

## تشغيل السكريبت

### عبر GitHub Actions (موصى به)
1. افتح تبويب **Actions**
2. اختر **Scrape Tafseer Sections**
3. اضغط **Run workflow**
4. اختياري: أدخل عدد السور للاختبار (مثلاً `3`)

### محلياً
```bash
pip install requests beautifulsoup4
python scraper_sections.py
```

لاختبار أول 3 سور فقط:
```bash
TEST_SURAHS=3 python scraper_sections.py
```

---

## التقنيات

- Python 3.9+
- [requests](https://pypi.org/project/requests/)
- [BeautifulSoup4](https://pypi.org/project/beautifulsoup4/)
- GitHub Actions

---

## المصدر

جميع المحتوى مستخرج من [dorar.net](https://dorar.net/tafseer) — موسوعة الدرر السنية.  
هذا المشروع أداة استخراج وتنظيم فقط، وليس بديلاً عن الموقع الأصلي.

---

## الترخيص

المحتوى العلمي: حقوق موسوعة الدرر السنية.  
كود الاستخراج: [MIT License](LICENSE).
