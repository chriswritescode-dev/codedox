import { useState, useEffect } from 'react';
import { useWebSocketContext } from '../contexts/WebSocketContext';
import { WebSocketMessageType } from '../lib/websocketTypes';

interface WebSocketMessage {
  type: string;
  job_id?: string;
  source_id?: string;
  [key: string]: any;
}

interface UseWebSocketSubscriptionOptions<T = any> {
  jobId?: string;
  sourceId?: string;
  messageType?: WebSocketMessageType | WebSocketMessageType[];
  filter?: (message: WebSocketMessage) => boolean;
  transform?: (message: WebSocketMessage) => T;
  enabled?: boolean;
}

export function useWebSocketSubscription<T = any>({
  jobId,
  sourceId,
  messageType,
  filter,
  transform,
  enabled = true,
}: UseWebSocketSubscriptionOptions<T> = {}) {
  const { subscribe, unsubscribe, addMessageListener, isConnected } = useWebSocketContext();
  const [data, setData] = useState<T | null>(null);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);

  useEffect(() => {
    if (!enabled) return;

    const subscriptionId = jobId || sourceId;
    if (subscriptionId) {
      subscribe(subscriptionId);
    }

    const handleMessage = (message: WebSocketMessage) => {
      const messageTypes = Array.isArray(messageType) ? messageType : messageType ? [messageType] : null;
      
      const typeMatches = !messageTypes || messageTypes.includes(message.type as WebSocketMessageType);
      const jobMatches = !jobId || message.job_id === jobId;
      const sourceMatches = !sourceId || message.source_id === sourceId;
      const customFilterMatches = !filter || filter(message);

      if (typeMatches && jobMatches && sourceMatches && customFilterMatches) {
        setLastMessage(message);
        
        if (transform) {
          setData(transform(message));
        } else {
          setData(message as T);
        }
      }
    };

    const removeListener = addMessageListener(handleMessage);

    return () => {
      removeListener();
      if (subscriptionId) {
        unsubscribe(subscriptionId);
      }
    };
  }, [jobId, sourceId, messageType, filter, transform, enabled, subscribe, unsubscribe, addMessageListener]);

  return {
    data,
    lastMessage,
    isConnected,
    reset: () => {
      setData(null);
      setLastMessage(null);
    },
  };
}
