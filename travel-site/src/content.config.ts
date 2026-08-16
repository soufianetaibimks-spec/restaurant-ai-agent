import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const articles = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/articles' }),
  schema: ({ image }) =>
    z.object({
      title: z.string(),
      description: z.string(),
      pubDate: z.coerce.date(),
      updatedDate: z.coerce.date().optional(),
      heroImage: image().optional(),
      heroImageAlt: z.string().optional(),
      destination: z.string(),
      country: z.string(),
      tags: z.array(z.string()).default([]),
      author: z.string().default('فريق التحرير'),
      readingTime: z.string().optional(),
      featured: z.boolean().default(false),
    }),
});

export const collections = { articles };
