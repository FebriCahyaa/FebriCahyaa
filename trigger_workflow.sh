curl -X PUT -H "Authorization: token ${{ secrets.TOKEN }}" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/${{ secrets.USERNAME }}/${{ secrets.REPO }}/contents/${{ secrets.PATH_TO_FILE }} \
  -d '{"message": "Update file trigger.txt", "content": "'$(date +%s)'", "branch": "main"}'
  
