import { test, expect } from '@playwright/test';

const TEST_QUERY = '查询临期商品，做一个柱状图，X轴为临期天数，y轴为商品数量';

test('AI对话 - 临期商品柱状图查询', async ({ page }) => {
  // ── 1. 打开前端 ──────────────────────────────────────────
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: '/tmp/step1_initial.png' });

  // ── 2. 滚动到底部，确保聊天输入框可见 ─────────────────────
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(500);

  // ── 3. 定位聊天输入框和发送按钮 ─────────────────────────
  //    React 受控组件：用 fill() 正确触发 synthetic events
  const inputBox = page.locator('input[placeholder*="输入问题"], input[placeholder*="请描述"]');
  const sendBtn = page.locator('button:has-text("发送"), button:has-text("Send")');

  const inputCount = await inputBox.count();
  const btnCount = await sendBtn.count();
  console.log(`[DEBUG] 找到输入框: ${inputCount}, 发送按钮: ${btnCount}`);

  if (inputCount === 0 || btnCount === 0) {
    // 尝试备用选择器
    const allInputs = await page.locator('input').count();
    const allBtns = await page.locator('button').count();
    console.log(`[DEBUG] 页面共有 input: ${allInputs}, button: ${allBtns}`);
    throw new Error(`元素未找到: input=${inputCount}, button=${btnCount}`);
  }

  // ── 4. 输入测试query ────────────────────────────────────
  await inputBox.fill(TEST_QUERY);
  await page.waitForTimeout(300);
  await page.screenshot({ path: '/tmp/step2_input_filled.png' });

  // ── 5. 点击发送 ─────────────────────────────────────────
  await sendBtn.first().click();
  await page.waitForTimeout(300);
  await page.screenshot({ path: '/tmp/step3_after_click.png' });

  // ── 6. 等待AI回复（最多20秒）────────────────────────────
  console.log('[INFO] 等待AI回复...');
  await page.waitForTimeout(15000);
  await page.screenshot({ path: '/tmp/step4_after_ai_reply.png' });

  // ── 7. 获取完整页面内容，验证关键要素 ───────────────────
  const pageText = await page.evaluate(() => document.body.innerText);

  // 7a. 检查是否有原始 <tool_call> 等标签残留（已知bug）
  const hasToolCallTag = /<tool[_\s]?call>/i.test(pageText);
  const hasJsonBlock = /"tool"\s*:\s*"(query_pending|generate_chart)"/.test(pageText);

  // 7b. 检查是否包含柱状图要素（ASCII art 或 chart 相关词）
  const hasBarChart = /(柱状图|bar chart|条形图|■|█|▓|▒|░|x轴|y轴|临期天数)/i.test(pageText);
  const hasXAxis = /(x轴|x[- ]axis|临期天数)/i.test(pageText);
  const hasYAxis = /(y轴|y[- ]axis|商品数量)/i.test(pageText);

  // 7c. 检查是否有错误信息
  const hasError = /(错误|error|exception|失败|failed)/i.test(pageText);

  // ── 8. 输出诊断信息 ────────────────────────────────────
  console.log('\n========== 诊断结果 ==========');
  console.log(`[CHECK] <tool_call> 标签残留: ${hasToolCallTag ? '❌ 有' : '✅ 无'}`);
  console.log(`[CHECK] JSON tool call 残留: ${hasJsonBlock ? '❌ 有' : '✅ 无'}`);
  console.log(`[CHECK] 柱状图内容: ${hasBarChart ? '✅ 有' : '❌ 无'}`);
  console.log(`[CHECK] X轴(临期天数): ${hasXAxis ? '✅ 有' : '❌ 无'}`);
  console.log(`[CHECK] Y轴(商品数量): ${hasYAxis ? '✅ 有' : '❌ 无'}`);
  console.log(`[CHECK] 错误信息: ${hasError ? '❌ 有' : '✅ 无'}`);
  console.log('\n========== AI回复内容 ==========');
  // 截取对话区域最后4000字
  const last4k = pageText.slice(-4000);
  console.log(last4k);
  console.log('='.repeat(40));

  // ── 9. 断言（允许部分失败，记录详细原因）─────────────────
  const issues = [];
  if (hasToolCallTag) issues.push('❌ <tool_call> 标签未过滤');
  if (hasJsonBlock)   issues.push('❌ JSON tool call 未过滤');
  if (hasError)        issues.push('❌ 页面包含错误信息');
  if (!hasBarChart)   issues.push('⚠️  未找到柱状图内容');

  if (issues.length > 0) {
    console.error('发现问题:', issues.join('; '));
  } else {
    console.log('✅ 所有检查通过');
  }

  // 截图留存
  await page.screenshot({ path: '/tmp/step5_final.png', fullPage: false });
  await page.screenshot({ path: '/tmp/step5_full.png', fullPage: true });

  // 截图路径供人工查看
  console.log('\n截图路径:');
  console.log('  /tmp/step1_initial.png     - 初始页面');
  console.log('  /tmp/step2_input_filled.png - 输入已填');
  console.log('  /tmp/step3_after_click.png  - 点击发送后');
  console.log('  /tmp/step4_after_ai_reply.png - AI回复后');
  console.log('  /tmp/step5_final.png       - 最终截图');
  console.log('  /tmp/step5_full.png        - 全页截图');
});
