import { resolve } from 'path'
export default {
  build: {
    rollupOptions: {
      input: {
        main:    resolve(__dirname, 'index.html'),
        expense: resolve(__dirname, 'expense.html'),
      },
    },
  },
}
