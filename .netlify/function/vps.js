// netlify/functions/vps.js
// API tạo VM từ GitHub - Bản hoàn chỉnh

let vms = [];

exports.handler = async (event, context) => {
  // CORS headers
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json'
  };

  // OPTIONS preflight
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers, body: '' };
  }

  // GET - Lấy danh sách VM
  if (event.httpMethod === 'GET') {
    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({ success: true, vms: vms })
    };
  }

  // DELETE - Xóa VM
  if (event.httpMethod === 'DELETE') {
    const id = event.queryStringParameters?.id;
    if (id) {
      vms = vms.filter(v => v.id !== id);
    }
    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({ success: true })
    };
  }

  // POST - Tạo VM (GỌI GITHUB THẬT)
  if (event.httpMethod === 'POST') {
    try {
      const body = JSON.parse(event.body || '{}');
      const { githubToken, tailscaleKey, vmUsername, vmPassword } = body;

      // Kiểm tra token
      if (!githubToken) {
        return {
          statusCode: 200,
          headers,
          body: JSON.stringify({ success: false, error: 'Vui lòng nhập GitHub Token' })
        };
      }

      if (!tailscaleKey) {
        return {
          statusCode: 200,
          headers,
          body: JSON.stringify({ success: false, error: 'Vui lòng nhập Tailscale Key' })
        };
      }

      const username = vmUsername || 'user_' + Math.floor(Math.random() * 10000);
      const password = vmPassword || 'Pass@' + Math.random().toString(36).substring(2, 12);

      let repoUrl = null;
      let workflowUrl = null;
      let status = 'creating';
      let errorMsg = null;
      let owner = null;

      try {
        // BƯỚC 1: Xác thực GitHub Token
        console.log('🔑 Validating GitHub token...');
        const userRes = await fetch('https://api.github.com/user', {
          headers: { 'Authorization': `Bearer ${githubToken}` }
        });
        const user = await userRes.json();

        if (!user.login) {
          status = 'failed';
          errorMsg = 'Token GitHub không hợp lệ hoặc đã hết hạn';
        } else {
          owner = user.login;
          console.log(`✅ GitHub user: ${owner}`);

          // BƯỚC 2: Tạo repository
          const repoName = 'vm-' + Date.now() + '-' + Math.random().toString(36).substring(2, 8);
          console.log(`📁 Creating repo: ${repoName}`);

          const createRes = await fetch('https://api.github.com/user/repos', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${githubToken}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              name: repoName,
              description: `Virtual Machine created by ${username}`,
              private: false,
              auto_init: true
            })
          });
          const repo = await createRes.json();

          if (repo.html_url) {
            repoUrl = repo.html_url;
            workflowUrl = `https://github.com/${owner}/${repoName}/actions`;
            status = 'running';
            console.log(`✅ Repo created: ${repoUrl}`);
          } else {
            status = 'failed';
            errorMsg = repo.message || 'Không thể tạo repository';
            console.log(`❌ Create repo failed: ${errorMsg}`);
          }
        }
      } catch (err) {
        status = 'failed';
        errorMsg = err.message;
        console.log(`❌ GitHub API error: ${errorMsg}`);
      }

      // Tạo VM record
      const newVM = {
        id: Date.now().toString() + '_' + Math.random().toString(36).substring(2, 6),
        name: 'vm-' + Date.now(),
        owner: owner,
        username: username,
        password: password,
        status: status,
        repoUrl: repoUrl,
        workflowUrl: workflowUrl,
        error: errorMsg,
        createdAt: new Date().toISOString(),
        expiresAt: new Date(Date.now() + 6 * 60 * 60 * 1000).toISOString()
      };

      vms = [newVM, ...vms];
      if (vms.length > 20) vms.pop();

      if (status === 'running') {
        return {
          statusCode: 200,
          headers,
          body: JSON.stringify({ 
            success: true, 
            ...newVM,
            message: `✅ VM "${username}" đã được tạo thành công!`
          })
        };
      } else {
        return {
          statusCode: 200,
          headers,
          body: JSON.stringify({ 
            success: false, 
            error: errorMsg,
            ...newVM
          })
        };
      }

    } catch (error) {
      console.log('❌ Server error:', error);
      return {
        statusCode: 200,
        headers,
        body: JSON.stringify({ success: false, error: error.message })
      };
    }
  }

  return {
    statusCode: 200,
    headers,
    body: JSON.stringify({ success: false, error: 'Method not allowed' })
  };
};
