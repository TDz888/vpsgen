// functions/api/vps.js
// Cloudflare Pages Functions - KHÔNG cần import/export phức tạp

// Lưu trữ tạm (mỗi request là độc lập, dùng global cho demo)
let vms = [];

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  
  // CORS headers
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json'
  };
  
  // OPTIONS preflight
  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers });
  }
  
  // GET - Lấy danh sách VM
  if (request.method === 'GET') {
    return new Response(JSON.stringify({ success: true, vms: vms }), { headers });
  }
  
  // DELETE - Xóa VM
  if (request.method === 'DELETE') {
    const id = url.searchParams.get('id');
    if (id) {
      vms = vms.filter(v => v.id !== id);
    }
    return new Response(JSON.stringify({ success: true }), { headers });
  }
  
  // POST - Tạo VM
  if (request.method === 'POST') {
    try {
      const body = await request.json();
      const { githubToken, tailscaleKey, vmUsername, vmPassword } = body;
      
      // Kiểm tra token cơ bản
      if (!githubToken) {
        return new Response(JSON.stringify({ success: false, error: 'Thiếu GitHub Token' }), { headers, status: 200 });
      }
      if (!tailscaleKey) {
        return new Response(JSON.stringify({ success: false, error: 'Thiếu Tailscale Key' }), { headers, status: 200 });
      }
      
      const username = vmUsername || 'user_' + Math.floor(Math.random() * 10000);
      const password = vmPassword || 'Pass@' + Math.random().toString(36).substring(2, 12);
      
      // Tạo VM mới
      const newVM = {
        id: Date.now().toString(),
        name: 'vm-' + Date.now(),
        username: username,
        password: password,
        status: 'creating',
        createdAt: new Date().toISOString(),
        expiresAt: new Date(Date.now() + 6 * 60 * 60 * 1000).toISOString(),
        message: 'VM đang được tạo...'
      };
      
      // GỌI GITHUB API TRỰC TIẾP
      try {
        // 1. Xác thực token
        const userRes = await fetch('https://api.github.com/user', {
          headers: { 'Authorization': `Bearer ${githubToken}` }
        });
        const user = await userRes.json();
        
        if (!user.login) {
          newVM.status = 'failed';
          newVM.error = 'Token GitHub không hợp lệ';
          vms = [newVM, ...vms];
          return new Response(JSON.stringify({ success: false, error: 'Token GitHub không hợp lệ' }), { headers });
        }
        
        // 2. Tạo repository
        const repoName = 'vm-' + Date.now();
        const createRepo = await fetch('https://api.github.com/user/repos', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${githubToken}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            name: repoName,
            description: `VM by ${username}`,
            private: false,
            auto_init: true
          })
        });
        
        const repo = await createRepo.json();
        
        if (!repo.full_name) {
          newVM.status = 'failed';
          newVM.error = 'Tạo repository thất bại';
        } else {
          newVM.status = 'running';
          newVM.repoUrl = repo.html_url;
          newVM.message = 'VM đã được tạo thành công!';
        }
        
      } catch(githubError) {
        newVM.status = 'failed';
        newVM.error = githubError.message;
      }
      
      vms = [newVM, ...vms];
      if (vms.length > 20) vms.pop();
      
      return new Response(JSON.stringify({ success: true, ...newVM }), { headers });
      
    } catch(error) {
      return new Response(JSON.stringify({ success: false, error: error.message }), { headers, status: 200 });
    }
  }
  
  return new Response(JSON.stringify({ success: false, error: 'Method not allowed' }), { headers, status: 200 });
}
