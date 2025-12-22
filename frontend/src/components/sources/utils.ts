export type SnippetBounds = {
  min: number | undefined
  max: number | undefined
}

export const getSnippetBounds = (snippetFilter: string): SnippetBounds => {
  switch (snippetFilter) {
    case "0":
      return { min: 0, max: 0 }
    case "has-snippets":
      return { min: 1, max: undefined }
    default:
      return { min: undefined, max: undefined }
  }
}
