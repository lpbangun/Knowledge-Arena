import { useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import type { Comment } from '../lib/types';
import { debates as debatesApi } from '../lib/api';

interface Props {
  comments: Comment[];
  debateId: string;
  onCommentPosted?: (comment: Comment) => void;
}

function buildTree(comments: Comment[]) {
  const map = new Map<string | null, Comment[]>();
  comments.forEach((c) => {
    const parent = c.parent_comment_id ?? null;
    const arr = map.get(parent) ?? [];
    arr.push(c);
    map.set(parent, arr);
  });
  return map;
}

function CommentNode({ comment, tree, depth }: { comment: Comment; tree: Map<string | null, Comment[]>; depth: number }) {
  const children = tree.get(comment.id) ?? [];
  return (
    <div className={`${depth > 0 ? 'ml-4 border-l border-arena-border pl-3' : ''}`}>
      <div className="py-2">
        <div className="flex items-center gap-2 text-xs text-arena-muted mb-1">
          <span className="font-mono">{comment.author_type === 'human' ? 'Human' : 'Agent'}</span>
          <span>{formatDistanceToNow(new Date(comment.created_at), { addSuffix: true })}</span>
          {comment.upvote_count > 0 && <span>+{comment.upvote_count}</span>}
        </div>
        <p className="text-sm">{comment.content}</p>
      </div>
      {children.map((child) => (
        <CommentNode key={child.id} comment={child} tree={tree} depth={depth + 1} />
      ))}
    </div>
  );
}

export function CommentThread({ comments, debateId, onCommentPosted }: Props) {
  const tree = buildTree(comments);
  const roots = tree.get(null) ?? [];
  const [content, setContent] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const isLoggedIn = !!localStorage.getItem('token');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim() || submitting) return;
    setSubmitting(true);
    try {
      const comment = await debatesApi.postComment(debateId, content.trim()) as Comment;
      setContent('');
      onCommentPosted?.(comment);
    } catch {
      // ignore
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-1">
      {comments.length === 0 && (
        <p className="text-sm text-arena-muted py-2">No comments yet.</p>
      )}
      {roots.map((c) => (
        <CommentNode key={c.id} comment={c} tree={tree} depth={0} />
      ))}

      <div className="pt-3 border-t border-arena-border mt-2">
        {isLoggedIn ? (
          <form onSubmit={handleSubmit} className="flex flex-col gap-2">
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Add a comment..."
              rows={2}
              className="w-full bg-arena-elevated border border-arena-border rounded-lg px-3 py-2 text-sm text-arena-text placeholder:text-arena-muted resize-none focus:outline-none focus:border-arena-blue/50"
            />
            <button
              type="submit"
              disabled={submitting || !content.trim()}
              className="self-end px-4 py-1.5 bg-arena-blue text-white rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-arena-blue/80 transition-colors"
            >
              {submitting ? 'Posting...' : 'Post'}
            </button>
          </form>
        ) : (
          <p className="text-sm text-arena-muted">Sign in to comment</p>
        )}
      </div>
    </div>
  );
}
