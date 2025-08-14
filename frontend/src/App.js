import React, { useState, useEffect, useRef } from "react";
import "./App.css";
import { getHistory, sendMessage, resetChat } from "./api";

function App() {
  const [history, setHistory] = useState([]);
  const [content, setContent] = useState("");
  const [selectedTags, setSelectedTags] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);

  // Load history on component mount
  useEffect(() => {
    loadHistory();
  }, []);

  // Scroll to bottom when history updates
  useEffect(() => {
    scrollToBottom();
  }, [history]);

  const loadHistory = async () => {
    try {
      const response = await getHistory();
      setHistory(response.history);
    } catch (err) {
      setError(`Failed to load history: ${err.message}`);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const toggleTag = (tag) => {
    setSelectedTags((prev) => {
      if (prev.includes(tag)) {
        return prev.filter((t) => t !== tag);
      } else {
        return [...prev, tag];
      }
    });
  };

  const handleSend = async () => {
    if (!content.trim() || selectedTags.length === 0 || isLoading) {
      return;
    }

    const messageContent = content.trim();
    const tagsToSend = [...selectedTags];
    
    // Generate temporary ID for user message
    const tempUserMessageId = `temp_${Date.now()}`;
    
    // Add user message immediately (optimistic update)
    const userMessage = {
      id: tempUserMessageId,
      author: "user",
      role: "user",
      content: messageContent,
      ts: Date.now(),
    };

    // Add user message and placeholder loading messages for each selected AI
    const loadingMessages = tagsToSend.map((tag, index) => ({
      id: `loading_${Date.now()}_${index}`,
      author: tag.slice(1), // Remove @ prefix
      role: "assistant",
      content: "Thinking...",
      ts: Date.now() + index + 1,
      isLoading: true,
    }));

    setHistory((prev) => [...prev, userMessage, ...loadingMessages]);
    
    // Clear content and set loading state
    setContent("");
    setIsLoading(true);
    setError(null);

    try {
      const response = await sendMessage(messageContent, tagsToSend);
      
      // Remove loading messages and add real responses
      setHistory((prev) => {
        // Remove the loading messages
        const withoutLoading = prev.filter(msg => !msg.isLoading);
        
        // Update user message with real ID from server
        const updatedHistory = withoutLoading.map(msg => 
          msg.id === tempUserMessageId 
            ? { ...msg, id: response.userMessageId }
            : msg
        );
        
        // Add real responses
        return [...updatedHistory, ...response.replies];
      });
      
    } catch (err) {
      setError(`Failed to send message: ${err.message}`);
      
      // Remove loading messages on error
      setHistory((prev) => prev.filter(msg => !msg.isLoading));
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = async () => {
    try {
      await resetChat();
      setHistory([]);
      setError(null);
    } catch (err) {
      setError(`Failed to reset chat: ${err.message}`);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      handleSend();
    }
  };

  const clearSelectedTags = () => {
    setSelectedTags([]);
  };

  const formatTimestamp = (ts) => {
    return new Date(ts).toLocaleTimeString();
  };

  const getAuthorColor = (author) => {
    switch (author) {
      case "user":
        return "bg-blue-100 text-blue-900 dark:bg-blue-900 dark:text-blue-100";
      case "gpt":
        return "bg-green-100 text-green-900 dark:bg-green-900 dark:text-green-100";
      case "claude":
        return "bg-purple-100 text-purple-900 dark:bg-purple-900 dark:text-purple-100";
      default:
        return "bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-gray-100";
    }
  };

  const getAuthorName = (author) => {
    switch (author) {
      case "user":
        return "You";
      case "gpt":
        return "GPT";
      case "claude":
        return "Claude";
      default:
        return author;
    }
  };

  const isErrorMessage = (content) => {
    return content.startsWith("(error from");
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="max-w-4xl mx-auto flex flex-col h-screen">
        {/* Header */}
        <div className="border-b border-border p-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold">3-Person Chat</h1>
          <button
            onClick={handleReset}
            className="px-4 py-2 text-sm bg-destructive text-destructive-foreground rounded-md hover:bg-destructive/90 transition-colors"
          >
            Reset Chat
          </button>
        </div>

        {/* Error Display */}
        {error && (
          <div className="p-4 bg-destructive/10 border border-destructive/20 text-destructive">
            {error}
          </div>
        )}

        {/* Chat History */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {history.length === 0 ? (
            <div className="text-center text-muted-foreground py-8">
              <p>No messages yet. Start a conversation!</p>
            </div>
          ) : (
            history.map((message) => (
              <div
                key={message.id}
                className={`flex ${
                  message.author === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[80%] rounded-lg p-4 ${
                    message.author === "user"
                      ? "bg-primary text-primary-foreground"
                      : getAuthorColor(message.author)
                  } ${
                    isErrorMessage(message.content)
                      ? "border-2 border-destructive bg-destructive/10 text-destructive"
                      : ""
                  } ${
                    message.isLoading
                      ? "animate-pulse bg-opacity-70"
                      : ""
                  }`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="font-semibold text-sm">
                      {getAuthorName(message.author)}
                    </span>
                    <span className="text-xs opacity-70">
                      {formatTimestamp(message.ts)}
                    </span>
                  </div>
                  <div className="whitespace-pre-wrap break-words">
                    {message.content}
                  </div>
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Composer */}
        <div className="border-t border-border p-4 space-y-4">
          {/* Tag Selection */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Select AI assistants:</span>
              {selectedTags.length > 0 && (
                <button
                  onClick={clearSelectedTags}
                  className="text-sm text-muted-foreground hover:text-foreground"
                >
                  Clear selection
                </button>
              )}
            </div>
            
            <div className="flex gap-2">
              <button
                onClick={() => toggleTag("@gpt")}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  selectedTags.includes("@gpt")
                    ? "bg-green-500 text-white"
                    : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
                }`}
              >
                @gpt
              </button>
              <button
                onClick={() => toggleTag("@claude")}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  selectedTags.includes("@claude")
                    ? "bg-purple-500 text-white"
                    : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
                }`}
              >
                @claude
              </button>
            </div>

            {/* Selected Tags Display */}
            {selectedTags.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Order:</span>
                {selectedTags.map((tag, index) => (
                  <React.Fragment key={tag}>
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        tag === "@gpt"
                          ? "bg-green-500 text-white"
                          : "bg-purple-500 text-white"
                      }`}
                    >
                      {tag}
                    </span>
                    {index < selectedTags.length - 1 && (
                      <span className="text-muted-foreground">→</span>
                    )}
                  </React.Fragment>
                ))}
              </div>
            )}
          </div>

          {/* Message Input */}
          <div className="flex gap-2">
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="Type your message... (Cmd/Ctrl+Enter to send)"
              className="flex-1 min-h-[100px] p-3 border border-input rounded-md bg-background resize-none focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
              disabled={isLoading}
            />
            <button
              onClick={handleSend}
              disabled={!content.trim() || selectedTags.length === 0 || isLoading}
              className="px-6 py-3 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors self-end"
            >
              {isLoading ? "Sending..." : "Send"}
            </button>
          </div>

          {/* Help Text */}
          <div className="text-xs text-muted-foreground">
            Select one or more AI assistants, type your message, and press Send or Cmd/Ctrl+Enter
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;