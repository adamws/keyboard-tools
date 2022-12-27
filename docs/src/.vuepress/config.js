import { defineUserConfig } from 'vuepress'
import { defaultTheme } from '@vuepress/theme-default'

export default defineUserConfig({
  title: 'Keyboard Tools',
  lang: 'en-US',
  base: '/keyboard-tools/',
  head: [['link', { rel: 'icon', href: '/keyboard-tools/images/favicon.ico' }]],
  theme: defaultTheme({
    home: "/",
    navbar: [
      {
        text: 'Github',
        link: 'https://github.com/adamws/keyboard-tools'
      }
    ],
    sidebar: {
      '/kicad-project-generator/': [
        {
          text: 'KiCad Project Generator',
          collapsable: false,
          children: [
            {
              text: 'Introduction',
              link: 'README.md'
            },
            'features',
            'examples',
            'guide',
            'development',
          ]
        }
      ],
    },
    lastUpdated: false,
    contributors: false,
    nextLinks: true,
    prevLinkgs: true,
  }),
})

