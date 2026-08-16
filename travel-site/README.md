# رحّالة — Travel Articles Site

موقع مقالات سفر مبني بـ [Astro](https://astro.build) + Markdown، بلا CMS ولا backend.

## البنية

- `src/content/articles/*.md` — المقالات (كل مقال ملف Markdown بـ frontmatter محدد فـ `src/content.config.ts`)
- `src/layouts/` — قالب الصفحة العامة وقالب المقال
- `src/components/ArticleCard.astro` — بطاقة المقال المستعملة فالصفحة الرئيسية وصفحة كل المقالات
- `src/pages/` — الصفحات: الرئيسية، `/articles`، `/articles/[id]`، `/about`، `/rss.xml`

## تشغيل المشروع محليا

```bash
npm install
npm run dev       # http://localhost:4321
npm run build      # يبني الموقع فـ dist/
npm run preview    # يعاين نسخة البناء النهائية
```

## زيادة مقال جديد

زيد ملف `.md` جديد فـ `src/content/articles/` بنفس الـ frontmatter اللي كاين فالمقالات الموجودة (title, description, pubDate, destination, country, tags, author...). الموقع كيقرا المقالات أوتوماتيكيا، ما خاصك تبدل حتى كود.

## الخطوات الجايين (اقتراحات)

- إضافة صور حقيقية للمقالات (`heroImage` فالـ frontmatter، الحقل معطى فـ schema)
- ربط دومين خاص وتحديث `site` فـ `astro.config.mjs`
- إضافة صفحات تصنيف حسب البلد/الوجهة
- نشر الموقع (Vercel, Netlify, ولا Cloudflare Pages كلهم كيدعمو Astro مباشرة)
