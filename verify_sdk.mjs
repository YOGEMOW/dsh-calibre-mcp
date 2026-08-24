// 用官方 MCP TypeScript SDK 验证 calibre-mcp-server 的 stdio 协议与工具调用。
const SDK = 'file:///C:/Users/YOGIMOV/.dsh/profiles/node_modules/@modelcontextprotocol/sdk/dist/esm';

const { Client } = await import(`${SDK}/client/index.js`);
const { StdioClientTransport } = await import(`${SDK}/client/stdio.js`);

const client = new Client({ name: 'verify-calibre-mcp', version: '1.0.0' });
const transport = new StdioClientTransport({
  command: 'C:/Users/YOGIMOV/AppData/Local/Programs/Python/Python310/python.exe',
  args: ['E:/DSH-workspace/calibre-mcp/server.py'],
});

await client.connect(transport);
console.log('CONNECTED');

const { tools } = await client.listTools();
console.log('TOOLS(' + tools.length + '):', tools.map((t) => t.name).join(', '));

const r = await client.callTool({
  name: 'search_books',
  arguments: { query: 'title:三体 OR title:Quick', limit: 3 },
});
console.log('SEARCH RESULT:');
for (const c of r.content) console.log(String(c.text).slice(0, 1500));

const stats = await client.callTool({ name: 'get_library_stats', arguments: {} });
console.log('STATS:', stats.content[0].text);

const read = await client.callTool({ name: 'read_book_text', arguments: { book_id: 1, max_chars: 400 } });
console.log('READ_TEXT:', String(read.content[0].text).slice(0, 300));

const allText = JSON.stringify([r, stats, read].map((x) => x.content[0].text));
console.log('NO_REPLACEMENT_CHARS:', !allText.includes('\ufffd'));

await client.close();
console.log('CLOSED OK');
