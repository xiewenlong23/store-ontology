import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ChatAssistant from '../src/components/ChatAssistant';

describe('ChatAssistant', () => {
  it('renders input field and send button', () => {
    render(<ChatAssistant />);

    const input = screen.getByPlaceholderText('输入问题或指令...');
    expect(input).toBeDefined();

    const button = screen.getByRole('button', { name: '发送' });
    expect(button).toBeDefined();
  });

  it('renders empty messages initially', () => {
    const { container } = render(<ChatAssistant />);
    const messages = container.querySelectorAll('.rounded-lg');
    // No user/assistant messages yet
    expect(messages.length).toBe(0);
  });
});
