package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"sync"

	"github.com/google/uuid"
)

const protocolVersion = "2025-11-25"

var sessionMgr = newSessionManager()

// rpcRequest 描述 MCP 客户端发送的 JSON-RPC 请求结构。
type rpcRequest struct {
	JSONRPC string  `json:"jsonrpc"`
	ID      any     `json:"id"`
	Method  string  `json:"method"`
	Params  *params `json:"params"`
}

type params struct {
	Name      string                 `json:"name"`
	Arguments map[string]interface{} `json:"arguments"`
}

// rpcResponse 始终返回 JSON-RPC 信封，携带 result 或 error。
type rpcResponse struct {
	JSONRPC string `json:"jsonrpc"`
	ID      any    `json:"id"`
	Result  any    `json:"result,omitempty"`
	Error   any    `json:"error,omitempty"`
}

type helloResult struct {
	Content  []contentItem     `json:"content"`
	Metadata map[string]string `json:"metadata"`
}

type contentItem struct {
	Type string `json:"type"`
	Text string `json:"text"`
}

// main 负责启动 HTTP 服务并挂载 MCP 相关路径。
func main() {
	port := flag.Int("port", 8000, "port to listen on")
	flag.Parse()

	addr := fmt.Sprintf(":%d", *port)
	http.HandleFunc("/", rootHandler)
	http.HandleFunc("/mcp", mcpEndpointHandler)

	log.Printf("Listening on http://0.0.0.0%s/mcp", addr)
	if err := http.ListenAndServe(addr, nil); err != nil {
		log.Fatalf("server error: %v", err)
	}
}

// rootHandler 提供一个简单的健康信号，让运维/Inspector 知道服务在线。
func rootHandler(w http.ResponseWriter, r *http.Request) {
	fmt.Fprintln(w, "MCP hello service ready. POST JSON-RPC to /mcp")
}

// mcpEndpointHandler 将 POST/GET/DELETE 三个 MCP 传输端点汇聚到一个处理函数。
func mcpEndpointHandler(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodPost:
		handlePost(w, r)
	case http.MethodGet:
		handleStream(w, r)
	case http.MethodDelete:
		handleDelete(w, r)
	default:
		w.Header().Set("Allow", "GET, POST, DELETE")
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

// handlePost 解码 JSON-RPC，分发 initialize、tools/list 和 tools/call。
func handlePost(w http.ResponseWriter, r *http.Request) {
	var req rpcRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, nil, -32700, "Parse error", err.Error(), http.StatusBadRequest, "")
		return
	}

	if req.JSONRPC != "2.0" {
		writeError(w, req.ID, -32600, "Only JSON-RPC 2.0 is supported", nil, http.StatusBadRequest, "")
		return
	}

	switch req.Method {
	case "initialize": // 初始化方法
		handleInitialize(w, r, req)
	case "notifications/initialized": // 初始化后会发这个通知，直接返回202，不反悔JSON-RPC body
		// JSON-RPC notification: no response body required.
		w.WriteHeader(http.StatusAccepted)
	case "tools/list":
		handleToolsList(w, r, req)
	case "tools/call":
		handleToolsCall(w, r, req)
	default:
		writeError(w, req.ID, -32601, "Method not found", req.Method, http.StatusNotFound, "")
	}
}

// handleInitialize 为每个客户端会话创建 session，并返回自身能力与指导语句。
func handleInitialize(w http.ResponseWriter, r *http.Request, req rpcRequest) {
	session := sessionMgr.create()
	w.Header().Set("MCP-Session-Id", session.id)
	w.Header().Set("Access-Control-Expose-Headers", "MCP-Session-Id")

	result := map[string]any{
		"protocolVersion": protocolVersion,
		"capabilities": map[string]any{
			"tools": map[string]any{"listChanged": true},
		},
		"serverInfo": map[string]any{
			"name":        "hello-mcp",
			"version":     "1.0",
			"description": "Simple hello tool demo",
		},
		"instructions": "Use tools/call/hello with optional user_name and greeting.",
	}

	resp := writeResponse(w, rpcResponse{
		JSONRPC: "2.0",
		ID:      req.ID,
		Result:  result,
	}, http.StatusOK)
	if resp != nil {
		sessionMgr.publish(session.id, resp)
	}
}

// handleToolsList 将支持的工具元数据返回给客户端，方便自动化列出可调用的工具。
func handleToolsList(w http.ResponseWriter, r *http.Request, req rpcRequest) {
	sessionID, ok := requireSessionID(w, r)
	if !ok {
		return
	}

	tool := map[string]any{
		"name":        "hello",
		"description": "Responds with a friendly greeting using the provided arguments.",
		"inputSchema": map[string]any{
			"type":                 "object",
			"additionalProperties": false,
			"properties": map[string]any{
				"user_name": map[string]any{"type": "string", "description": "Name of the person to greet"},
				"greeting":  map[string]any{"type": "string", "description": "Salutation text"},
			},
		},
	}

	resp := writeResponse(w, rpcResponse{
		JSONRPC: "2.0",
		ID:      req.ID,
		Result: map[string]any{
			"tools": []map[string]any{tool},
		},
	}, http.StatusOK)
	if resp != nil {
		sessionMgr.publish(sessionID, resp)
	}
}

// handleToolsCall 真正执行 hello 工具逻辑，并通过 session 返回结果与 SSE 推送。
func handleToolsCall(w http.ResponseWriter, r *http.Request, req rpcRequest) {
	sessionID, ok := requireSessionID(w, r)
	if !ok {
		return
	}

	if req.Params == nil || req.Params.Name != "hello" {
		writeError(w, req.ID, -32601, "Tool not found", req.Params.ParamsToString(), http.StatusNotFound, sessionID)
		return
	}

	name := stringValue(req.Params.Arguments, "user_name", "friend")
	greeting := stringValue(req.Params.Arguments, "greeting", "Hello")

	result := helloResult{
		Content: []contentItem{{
			Type: "text",
			Text: fmt.Sprintf("%s, %s! Welcome to the MCP hello service.", greeting, name),
		}},
		Metadata: map[string]string{
			"tool":    "hello",
			"version": "1.0",
			"note":    "Minimal sample tool",
		},
	}

	resp := writeResponse(w, rpcResponse{
		JSONRPC: "2.0",
		ID:      req.ID,
		Result:  result,
	}, http.StatusOK)
	if resp != nil {
		sessionMgr.publish(sessionID, resp)
	}
}

// handleStream 把 GET 请求变成一个 server-sent-events 流，用于向 Inspector 推送消息。
func handleStream(w http.ResponseWriter, r *http.Request) {
	sessionID := r.Header.Get("MCP-Session-Id")
	if sessionID == "" {
		http.Error(w, "missing MCP-Session-Id header", http.StatusBadRequest)
		return
	}

	session, ok := sessionMgr.get(sessionID)
	if !ok {
		http.Error(w, "session not found", http.StatusNotFound)
		return
	}

	_, events, cleanup := session.addListener()
	defer cleanup()

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("MCP-Session-Id", sessionID)
	w.Header().Set("Access-Control-Expose-Headers", "MCP-Session-Id")
	w.WriteHeader(http.StatusOK)

	flusher, ok := w.(http.Flusher)
	if ok {
		flusher.Flush()
	}

	notify := r.Context().Done()
	for {
		select {
		case <-notify:
			return
		case payload, ok := <-events:
			if !ok {
				return
			}
			fmt.Fprint(w, "event: mcp\n")
			fmt.Fprintf(w, "data: %s\n\n", payload)
			if flusher != nil {
				flusher.Flush()
			}
		}
	}
}

// handleDelete 接收客户端的 DELETE 请求，关闭对应 session 及相关流。
func handleDelete(w http.ResponseWriter, r *http.Request) {
	sessionID := r.Header.Get("MCP-Session-Id")
	if sessionID == "" {
		http.Error(w, "missing MCP-Session-Id header", http.StatusBadRequest)
		return
	}
	sessionMgr.delete(sessionID)
	w.WriteHeader(http.StatusOK)
}

// requireSessionID 抽象出检查 MCP-Session-Id 的步骤并处理错误响应。
func requireSessionID(w http.ResponseWriter, r *http.Request) (string, bool) {
	sessionID := r.Header.Get("MCP-Session-Id")
	if sessionID == "" {
		writeError(w, nil, -32600, "missing MCP-Session-Id header", nil, http.StatusBadRequest, "")
		return "", false
	}
	if _, ok := sessionMgr.get(sessionID); !ok {
		writeError(w, nil, -32000, "session not found", sessionID, http.StatusNotFound, "")
		return "", false
	}
	return sessionID, true
}

func (p *params) ParamsToString() string {
	if p == nil {
		return "<nil>"
	}
	return p.Name
}

func stringValue(args map[string]interface{}, key, fallback string) string {
	if args == nil {
		return fallback
	}
	if v, ok := args[key]; ok {
		if s, ok := v.(string); ok && s != "" {
			return s
		}
	}
	return fallback
}

// writeError 封装 JSON-RPC 错误返回，并可选地把错误发布到 SSE 流。
func writeError(w http.ResponseWriter, id any, code int, message string, data any, status int, sessionID string) {
	err := map[string]any{
		"code":    code,
		"message": message,
	}
	if data != nil {
		err["data"] = data
	}
	resp := writeResponse(w, rpcResponse{
		JSONRPC: "2.0",
		ID:      id,
		Error:   err,
	}, status)
	if resp != nil && sessionID != "" {
		sessionMgr.publish(sessionID, resp)
	}
}

// writeResponse 统一编码并写出 JSON-RPC 响应，返回原始字节以便复用。
func writeResponse(w http.ResponseWriter, payload any, status int) []byte {
	encoded, err := json.Marshal(payload)
	if err != nil {
		log.Printf("failed to encode response: %v", err)
		return nil
	}
	encoded = append(encoded, '\n')
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if _, err := w.Write(encoded); err != nil {
		log.Printf("failed to write response: %v", err)
	}
	return encoded
}

// sessionManager 管理所有活跃会话及其事件监听者。
type sessionManager struct {
	mu       sync.RWMutex
	sessions map[string]*session
}

type session struct {
	id        string
	mu        sync.Mutex
	listeners map[int]chan []byte
	nextID    int
	closed    bool
}

func newSessionManager() *sessionManager {
	return &sessionManager{sessions: make(map[string]*session)}
}

// create 为新的 MCP 会话生成唯一 ID 并注册。
func (m *sessionManager) create() *session {
	id := uuid.NewString()
	s := &session{id: id, listeners: make(map[int]chan []byte)}
	m.mu.Lock()
	m.sessions[id] = s
	m.mu.Unlock()
	return s
}

// get 按照 ID 查找会话并返回。
func (m *sessionManager) get(id string) (*session, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	s, ok := m.sessions[id]
	return s, ok
}

// delete 关闭会话并移除注册，防止事件继续推送。
func (m *sessionManager) delete(id string) {
	m.mu.Lock()
	if s, ok := m.sessions[id]; ok {
		delete(m.sessions, id)
		s.close()
	}
	m.mu.Unlock()
}

// publish 将响应事件广播到所有正在监听的 SSE 连接。
func (m *sessionManager) publish(id string, payload []byte) {
	s, ok := m.get(id)
	if !ok {
		return
	}
	s.publish(payload)
}

// addListener 为新的 SSE 连接注册监听通道。
func (s *session) addListener() (int, <-chan []byte, func()) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed {
		ch := make(chan []byte)
		close(ch)
		return -1, ch, func() {}
	}
	ch := make(chan []byte, 8)
	id := s.nextID
	s.nextID++
	s.listeners[id] = ch
	return id, ch, func() {
		s.removeListener(id)
	}
}

// removeListener 清理已经停止的监听。
func (s *session) removeListener(id int) {
	s.mu.Lock()
	if ch, ok := s.listeners[id]; ok {
		delete(s.listeners, id)
		close(ch)
	}
	s.mu.Unlock()
}

// publish 向所有监听通道广播事件（非阻塞）。
func (s *session) publish(payload []byte) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed {
		return
	}
	for _, ch := range s.listeners {
		select {
		case ch <- payload:
		default:
		}
	}
}

// close 彻底关闭 session，释放所有监听者并禁止后续事件。
func (s *session) close() {
	s.mu.Lock()
	if s.closed {
		s.mu.Unlock()
		return
	}
	s.closed = true
	for id, ch := range s.listeners {
		delete(s.listeners, id)
		close(ch)
	}
	s.mu.Unlock()
}
