#!/usr/bin/env node

/**
 * Shared slug generation utilities
 * Used across multiple skills for consistent slug creation
 */

function slugify(text) {
  return text
    .toString()
    .toLowerCase()
    .trim()
    .replace(/\s+/g, '-')
    .replace(/[^\w\-]+/g, '')
    .replace(/\-\-+/g, '-')
    .replace(/^-+/, '')
    .replace(/-+$/, '');
}

function createTitleSlug(title, orgName, location) {
  const parts = [title, orgName, location].filter(Boolean);
  return slugify(parts.join(' '));
}

function createSourceRef(orgSlug, jobTitle) {
  const year = new Date().getFullYear();
  const titleSlug = slugify(jobTitle);
  const randomSuffix = Math.floor(Math.random() * 900) + 100;
  const titlePart = titleSlug.split('-').slice(0, 2).join('');
  return `${orgSlug}-${year}-${titlePart}-${randomSuffix}`;
}

module.exports = {
  slugify,
  createTitleSlug,
  createSourceRef
};
