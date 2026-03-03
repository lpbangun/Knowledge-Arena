import { formatDistanceToNow } from 'date-fns';
import type { Comment } from '../lib/types';

interface Props {
  comments: Comment[];
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

export function CommentThread({ comments }: Props) {
  const tree = buildTree(comments);
  const roots = tree.get(null) ?? [];

  if (!comments.length) {
    return <p className="text-sm text-arena-muted py-2">No comments yet.</p>;
  }

  return (
    <div className="space-y-1">
      {roots.map((c) => (
        <CommentNode key={c.id} comment={c} tree={tree} depth={0} />
      ))}
    </div>
  );
}
