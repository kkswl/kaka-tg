// 构建前清理 dist 目录。
// Node 的 fs.rmSync(recursive:true) 在 Windows 上偶尔静默失败（返回成功但目录仍在），
// 故这里用手动递归 unlinkSync + rmdirSync，确保每次构建前 dist 被彻底清空，
// 避免 vite-plugin-federation 旧 hash 产物残留成孤儿文件。
import { existsSync, readdirSync, lstatSync, unlinkSync, rmdirSync } from 'fs'
import { join } from 'path'

function rmrf(p) {
  if (!existsSync(p)) return
  for (const entry of readdirSync(p)) {
    const cur = join(p, entry)
    if (lstatSync(cur).isDirectory()) rmrf(cur)
    else unlinkSync(cur)
  }
  rmdirSync(p)
}

rmrf('dist')
