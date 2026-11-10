/**
 * 老财剪辑 (dsh-laocai-editing)
 *
 * DeepSeek Harness host plugin that ships kelaocai's local video-editing and
 * subtitle skills as a bundled skill provider — the same pattern as the
 * official `dsh-skill-office` / `dsh-skill-badge` packages. It registers a
 * `SkillProvider` on `ctx.skills` whose candidates read `SKILL.md` from the
 * bundled `assets/` directory, and exposes each skill's `references/`,
 * `templates/` and `scripts/` through the provider's `resourceBase`, so the
 * `skill` tool resolves the skills' relative references correctly.
 *
 * The skills are pure Markdown instruction sets; this plugin only makes them
 * discoverable. It registers no prompt section, tool, or request field.
 */

import { readFileSync } from 'node:fs'
import { readFile } from 'node:fs/promises'
import { join, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

/**
 * `@deepseek-ai/dsh-skill` exports this constant as `BUNDLED_SKILL_RANK`.
 * It is the stable precedence rank for packaged skill providers and bundled
 * roots; inlining the value keeps this plugin free of runtime dependencies.
 */
const BUNDLED_SKILL_RANK = 600

/** Unique provider name within `ctx.skills` (must equal each candidate's `provider`). */
const PROVIDER_NAME = 'laocai-editing'

/** Both model auto-loading and user `/name` invocation are enabled. */
const INVOCATION = Object.freeze({ modelInvocable: true, userInvocable: true })

const ASSET_ROOT = fileURLToPath(new URL('./assets/', import.meta.url))
const MANIFEST_PATH = join(ASSET_ROOT, 'manifest.json')

/** Cordis plugin name. */
export const name = 'laocai-editing'

/** The skill registry is the only capability this plugin needs. */
export const inject = ['skills']

/**
 * Register the bundled skill provider on the mounting fiber.
 * @param {object} ctx - plugin context carrying `ctx.skills`.
 * @returns {void} registration is synchronous; disposal is owned by the fiber.
 */
export function apply(ctx) {
  const manifest = JSON.parse(readFileSync(MANIFEST_PATH, 'utf8'))

  const candidates = manifest.skills.map((entry) => {
    const directory = join(ASSET_ROOT, entry.dir)
    return {
      name: entry.name,
      description: entry.description,
      invocation: INVOCATION,
      provider: PROVIDER_NAME,
      source: 'bundled',
      rank: BUNDLED_SKILL_RANK,
      resourceBase: { kind: 'directory', path: directory.split(sep).join('/') },
      locator: join(directory, 'SKILL.md'),
    }
  })

  const provider = {
    name: PROVIDER_NAME,
    list: () => Promise.resolve(candidates),
    async get(candidate, options) {
      const { rank, locator, ...summary } = candidate
      const raw = await readFile(locator, { encoding: 'utf8', signal: options?.signal })
      return { ...summary, content: stripFrontmatter(raw) }
    },
  }

  ctx.skills.registerProvider(() => provider)
}

/**
 * Strip the leading YAML frontmatter block from a SKILL.md body, mirroring
 * the official `dsh-skill-office` parser.
 * @param {string} raw - full SKILL.md text.
 * @returns {string} body without the `--- ... ---` frontmatter.
 */
function stripFrontmatter(raw) {
  const match = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/u.exec(raw)
  if (match === null) {
    throw new Error('laocai-editing: SKILL.md has no YAML frontmatter')
  }
  return raw.slice(match[0].length).trim()
}
